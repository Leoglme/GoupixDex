"""Groq vision chat completions for Pokémon TCG card photo OCR-style extraction."""

from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Any, cast

import httpx
from PIL import Image, ImageOps

from app_types.groq_vision import GroqVisionCardCollectorResult, GroqVisionExtractOptions
from app_types.groq_vision import GroqVisionImageMimeType
from app_types.pokewallet import PokeWalletCard
from services.pokeapi_species_locale import fetch_species_locale_names
from services.pokewallet_client import PokeWalletClient

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
ENV_API_KEY = "GROQ_API_KEY"
ENV_POKE_WALLET_KEY = "POKE_WALLET_API_KEY"
DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_BASE64_IMAGE_BYTES = 4 * 1024 * 1024
CHAT_COMPLETIONS_PATH = "/chat/completions"
SET_CODE_CROP_MAX_COMPLETION_TOKENS = 64

RESIZE_LONG_EDGE_PX: tuple[int, ...] = (2048, 1600, 1280, 1024, 800, 640)
JPEG_QUALITY_STEPS: tuple[int, ...] = (88, 78, 68, 58, 48)


class GroqVisionClient:
    """
    Client for `Groq <https://console.groq.com/docs/vision>`_ vision chat completions.
    Extracts Pokémon TCG **set code**, **collector number**, **fraction parts**, and **Pokémon names**
    from card photos via OCR-style prompts. Optional PokéWallet lookup can enrich English names,
    ``set_name_english``, and ``rarity_english`` when ``resolve_english_name_from_poke_wallet`` is true.
    PokéAPI then supplies canonical French and (when missing) Japanese species names from English.
    Loads ``GROQ_API_KEY`` from the environment unless an explicit key is passed.
    """

    def __init__(self, api_key: str | None = None, base_url: str = DEFAULT_BASE_URL) -> None:
        """
        Args:
            api_key: Optional API key. If omitted, uses ``os.environ["GROQ_API_KEY"]``.
            base_url: Optional API base URL (defaults to Groq OpenAI-compatible root).

        Raises:
            ValueError: When no API key is available.
        """
        env_value = os.environ.get(ENV_API_KEY)
        resolved = api_key if api_key is not None else env_value
        if resolved is None:
            msg = f"Missing API key: set {ENV_API_KEY} in the environment or pass it to the constructor."
            raise ValueError(msg)
        trimmed_key = resolved.strip()
        if trimmed_key == "":
            msg = f"Missing API key: set {ENV_API_KEY} in the environment or pass it to the constructor."
            raise ValueError(msg)
        self._api_key = trimmed_key
        self._base_url = base_url.rstrip("/")

    def extract_card_collector_from_image_path(
        self,
        image_path: str,
        options: GroqVisionExtractOptions | None = None,
    ) -> GroqVisionCardCollectorResult:
        """
        Read an image file from disk, encode it as a data URL, and extract collector fields.

        Args:
            image_path: Absolute or relative path to a JPEG, PNG, or WebP file.
            options: Optional model override, temperature, and debug flags.

        Raises:
            ValueError: When the path is empty after trim.
            OSError: When the file cannot be read.
            RuntimeError: When the payload still exceeds Groq limits or the API response is invalid.
        """
        trimmed = str(image_path).strip()
        if trimmed == "":
            msg = "extract_card_collector_from_image_path: image_path must be non-empty after trim."
            raise ValueError(msg)
        path = Path(trimmed)
        data = path.read_bytes()
        mime = self._resolve_mime_type_from_path(str(path))
        return self.extract_card_collector_from_image_bytes(data, mime, options)

    def extract_card_collector_from_image_bytes(
        self,
        data: bytes,
        mime_type: GroqVisionImageMimeType,
        options: GroqVisionExtractOptions | None = None,
    ) -> GroqVisionCardCollectorResult:
        """
        Send raw image bytes to Groq vision and return structured collector fields.

        Args:
            data: Raw image file bytes (JPEG, PNG, or WebP).
            mime_type: MIME type for the data URL.
            options: Optional model override, temperature, and debug flags.

        Raises:
            RuntimeError: When the image cannot be shrunk under Groq limits or the API response is invalid.
        """
        payload_bytes = data
        payload_mime: GroqVisionImageMimeType = mime_type
        initial_b64 = base64.b64encode(payload_bytes).decode("ascii")
        initial_data_url = f"data:{payload_mime};base64,{initial_b64}"
        if len(initial_data_url.encode("utf-8")) > MAX_BASE64_IMAGE_BYTES:
            payload_bytes = self._shrink_image_bytes_for_groq_limit(data)
            payload_mime = "image/jpeg"
        b64 = base64.b64encode(payload_bytes).decode("ascii")
        data_url = f"data:{payload_mime};base64,{b64}"
        if len(data_url.encode("utf-8")) > MAX_BASE64_IMAGE_BYTES:
            n = len(data_url.encode("utf-8"))
            msg = (
                f"Groq vision: data URL still exceeds {MAX_BASE64_IMAGE_BYTES} bytes ({n}) after compression."
            )
            raise RuntimeError(msg)

        collector = self.extract_card_collector_from_data_url(data_url, options)
        refined_raw = self._extract_set_code_from_bottom_left_crop(
            payload_bytes,
            payload_mime,
            options,
        )
        refined_value = refined_raw.strip() if refined_raw else None
        cur_code = collector.get("set_code")
        cur_trim = (cur_code or "").strip()
        # Only fill from the tight bottom-left crop when the primary pass did not yield a set code.
        # Replacing a non-empty primary value often regresses (e.g. misreading SV5a as SV4K on tiny glyphs).
        needs_refresh = (
            refined_value is not None
            and refined_value != ""
            and cur_trim == ""
            and self._should_override_set_code(cur_code, refined_value)
        )
        if not needs_refresh:
            return collector
        out = dict(collector)
        out["set_code"] = refined_value
        merged = cast(GroqVisionCardCollectorResult, out)
        merged = self._apply_poke_wallet_enrichment(merged, options)
        return self._apply_pokeapi_species_locale_names(merged, options)

    def extract_card_collector_from_data_url(
        self,
        data_url: str,
        options: GroqVisionExtractOptions | None = None,
    ) -> GroqVisionCardCollectorResult:
        """
        Extract collector fields from an already-encoded ``data:image/...;base64,...`` URL.

        Args:
            data_url: Full data URL including the ``data:`` scheme and base64 payload.
            options: Optional model override, temperature, and debug flags.
        """
        trimmed = data_url.strip()
        if trimmed == "":
            msg = "extract_card_collector_from_data_url: data_url must be non-empty after trim."
            raise ValueError(msg)
        payload_len = len(trimmed.encode("utf-8"))
        if payload_len > MAX_BASE64_IMAGE_BYTES:
            msg = f"Groq vision: data URL exceeds {MAX_BASE64_IMAGE_BYTES} bytes ({payload_len})."
            raise RuntimeError(msg)

        opts = options or {}
        model = opts.get("model", DEFAULT_MODEL)
        temperature = float(opts.get("temperature", 0))
        include_raw = opts.get("include_raw_assistant_json") is True
        hint = self._normalize_user_hint(opts.get("user_hint"))

        body: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "max_completion_tokens": 768,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._build_user_prompt(hint)},
                        {"type": "image_url", "image_url": {"url": trimmed}},
                    ],
                },
            ],
        }
        url = f"{self._base_url}{CHAT_COMPLETIONS_PATH}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        response = httpx.post(url, headers=headers, json=body, timeout=120.0)
        body_text = response.text
        if not response.is_success:
            msg = f"Groq request failed ({response.status_code} {response.reason_phrase}): {body_text}"
            raise RuntimeError(msg)
        parsed = self._parse_json_body(body_text)
        content = self._pick_assistant_content(parsed)
        if content is None or content == "":
            raise RuntimeError("Groq response contained no assistant message content.")

        collector = self._parse_collector_result_json(content)
        collector = self._apply_poke_wallet_enrichment(collector, options)
        collector = self._apply_pokeapi_species_locale_names(collector, options)
        if include_raw:
            out = dict(collector)
            out["raw_assistant_json"] = content
            return cast(GroqVisionCardCollectorResult, out)
        return collector

    @staticmethod
    def _should_override_set_code(current_set_code: str | None, refined_set_code: str) -> bool:
        current = (current_set_code or "").strip().upper()
        refined = refined_set_code.strip().upper()
        if current == "":
            return True
        if re.match(r"^[A-Z][0-9][A-Z]$", refined):
            return True
        if current.startswith("SV") and refined.startswith("SV"):
            return True
        if len(refined) <= 2:
            return False
        return True

    def _apply_poke_wallet_enrichment(
        self,
        collector: GroqVisionCardCollectorResult,
        options: GroqVisionExtractOptions | None,
    ) -> GroqVisionCardCollectorResult:
        opts = options or {}
        if opts.get("resolve_english_name_from_poke_wallet") is not True:
            return collector
        card_number = collector.get("card_number")
        if not card_number:
            return collector
        lookup_numbers = self._build_card_number_lookup_candidates(card_number)
        env_val = os.environ.get(ENV_POKE_WALLET_KEY, "").strip()
        proxy_secret = os.environ.get("POKE_WALLET_PROXY_SECRET", "").strip()
        if env_val == "" and proxy_secret == "":
            return collector
        try:
            wallet = PokeWalletClient()
        except ValueError:
            return collector
        set_code = collector.get("set_code")
        first: PokeWalletCard | None = None
        hint = self._normalize_user_hint(opts.get("user_hint"))

        if set_code:
            for lookup_number in lookup_numbers:
                by_set = wallet.search_by_set_code_and_number(
                    set_code,
                    lookup_number,
                    {"limit": 8, "page": 1},
                )
                results = by_set.get("results", [])
                if results:
                    first = self._pick_best_wallet_result(results, collector, hint)
                    break

        english_hint_raw = (collector.get("pokemon_name_english") or "").strip()
        english_hint = english_hint_raw or None
        if first is None and english_hint:
            for lookup_number in lookup_numbers:
                by_name = wallet.search(f"{english_hint} {lookup_number}", {"limit": 15, "page": 1})
                results = by_name.get("results", [])
                if results:
                    first = self._pick_best_wallet_result(results, collector, hint)
                    break

        printed_raw = (collector.get("pokemon_name") or "").strip()
        printed_name = printed_raw or None
        printed_differs = (
            printed_name is not None
            and english_hint is not None
            and printed_name != english_hint
        )
        printed_usable = printed_name is not None and english_hint is None
        if first is None and printed_name and (printed_differs or printed_usable):
            for lookup_number in lookup_numbers:
                by_printed = wallet.search(f"{printed_name} {lookup_number}", {"limit": 15, "page": 1})
                results = by_printed.get("results", [])
                if results:
                    first = self._pick_best_wallet_result(results, collector, hint)
                    break

        if first is None:
            for lookup_number in lookup_numbers:
                by_num = wallet.search(lookup_number, {"limit": 25, "page": 1})
                results = by_num.get("results", [])
                if results:
                    first = self._pick_best_wallet_result(results, collector, hint)
                    break

        if first is None:
            return collector

        info = first["card_info"]
        clean_preferred = (info.get("clean_name") or "").strip()
        name_fallback = (info.get("name") or "").strip()
        raw_product = clean_preferred if clean_preferred else (name_fallback or None)
        pokemon_name_english = collector.get("pokemon_name_english")
        if raw_product:
            stripped = self._strip_trailing_collector_suffix_from_product_name(raw_product)
            if stripped:
                pokemon_name_english = stripped

        set_name_raw = (info.get("set_name") or "").strip()
        set_name_from_api_or_vision = (
            set_name_raw if set_name_raw else collector.get("set_name_english")
        )
        api_set_code_raw = (info.get("set_code") or "").strip()
        canonical_set_code = api_set_code_raw if api_set_code_raw else set_code
        strip_code = canonical_set_code if canonical_set_code else (set_code or "")
        if set_name_from_api_or_vision and str(set_name_from_api_or_vision).strip():
            sn = str(set_name_from_api_or_vision).strip()
            set_name_english = (
                self._strip_leading_set_code_prefix_from_set_name(sn, strip_code)
                if strip_code
                else sn
            )
        else:
            set_name_english = None

        rarity_raw = (info.get("rarity") or "").strip()
        rarity_english = rarity_raw if rarity_raw else collector.get("rarity_english")

        existing_set_code = collector.get("set_code")
        normalized_existing_set = (
            self._normalize_set_code_case(existing_set_code) if existing_set_code else None
        )
        normalized_api_set = self._normalize_set_code_case(api_set_code_raw) if api_set_code_raw else None
        resolved_set_code = normalized_existing_set
        if normalized_api_set is not None and (
            normalized_existing_set is None or normalized_existing_set == normalized_api_set
        ):
            resolved_set_code = normalized_api_set
        card_number_raw = (info.get("card_number") or "").strip()
        existing_card_number = collector.get("card_number")
        resolved_card_number = existing_card_number
        if card_number_raw and (
            existing_card_number is None
            or self._normalize_card_number(existing_card_number)
            == self._normalize_card_number(card_number_raw)
        ):
            resolved_card_number = card_number_raw
        split = self._split_card_collector_fraction(resolved_card_number)

        return cast(
            GroqVisionCardCollectorResult,
            {
                **collector,
                "set_code": resolved_set_code,
                "card_number": resolved_card_number,
                "card_number_numerator": split["card_number_numerator"],
                "card_number_denominator": split["card_number_denominator"],
                "pokemon_name_english": pokemon_name_english,
                "set_name_english": set_name_english,
                "rarity_english": rarity_english,
            },
        )

    def _apply_pokeapi_species_locale_names(
        self,
        collector: GroqVisionCardCollectorResult,
        options: GroqVisionExtractOptions | None,
    ) -> GroqVisionCardCollectorResult:
        """Overwrite French with PokéAPI when possible; fill Japanese ``pokemon_name`` when still empty."""
        opts = options or {}
        if opts.get("resolve_english_name_from_poke_wallet") is not True:
            return collector
        english_raw = (collector.get("pokemon_name_english") or "").strip()
        if not english_raw:
            return collector
        loc = fetch_species_locale_names(english_raw)
        if loc.french is None and loc.japanese is None:
            return collector
        out = dict(collector)
        if loc.french is not None:
            out["pokemon_name_french"] = loc.french
        printed = (out.get("pokemon_name") or "").strip()
        if loc.japanese is not None and printed == "":
            out["pokemon_name"] = loc.japanese
        return cast(GroqVisionCardCollectorResult, out)

    def _strip_leading_set_code_prefix_from_set_name(self, raw_set_name: str, set_code: str) -> str:
        trimmed_name = raw_set_name.strip()
        trimmed_code = set_code.strip()
        if trimmed_code == "":
            return trimmed_name
        escaped = re.escape(trimmed_code)
        pattern = re.compile(rf"^{escaped}\s*:\s*", re.IGNORECASE)
        stripped = pattern.sub("", trimmed_name).strip()
        if stripped == "":
            return trimmed_name
        return stripped

    @staticmethod
    def _strip_trailing_collector_suffix_from_product_name(raw: str) -> str:
        s = raw.strip()
        patterns = [
            re.compile(r"\s*[-–—]\s*\d+\s*/\s*\d+\s*$", re.UNICODE),
            re.compile(r"\s*[-–—]\s*\d+\s+\d+\s*$", re.UNICODE),
            re.compile(r"\s+\d+\s*/\s*\d+\s*$", re.UNICODE),
            re.compile(r"\s+\d+\s+\d+\s*$", re.UNICODE),
            re.compile(r"\s*\(\s*\d+\s*/\s*\d+\s*\)\s*$", re.UNICODE),
            re.compile(r"\s*\(\s*\d+\s+\d+\s*\)\s*$", re.UNICODE),
        ]
        for pat in patterns:
            s = pat.sub("", s).strip()
        return s

    def _shrink_image_bytes_for_groq_limit(self, source: bytes) -> bytes:
        last_too_large: int | None = None
        last_sharp_error: str | None = None
        for max_edge in RESIZE_LONG_EDGE_PX:
            for quality in JPEG_QUALITY_STEPS:
                try:
                    buf = io.BytesIO(source)
                    img = Image.open(buf)
                    img = ImageOps.exif_transpose(img)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                    out_buf = io.BytesIO()
                    img.save(out_buf, format="JPEG", quality=quality, optimize=True)
                    out = out_buf.getvalue()
                    candidate_url = f"data:image/jpeg;base64,{base64.b64encode(out).decode('ascii')}"
                    if len(candidate_url.encode("utf-8")) <= MAX_BASE64_IMAGE_BYTES:
                        return out
                    last_too_large = len(candidate_url.encode("utf-8"))
                except OSError as exc:
                    last_sharp_error = str(exc)
        length_hint = f" Last attempt length: {last_too_large}." if last_too_large else ""
        sharp_hint = f" Pillow error: {last_sharp_error}" if last_sharp_error else ""
        msg = (
            f"Groq vision: could not compress image under {MAX_BASE64_IMAGE_BYTES} bytes (data URL)."
            f"{length_hint}{sharp_hint}"
        )
        raise RuntimeError(msg)

    def _extract_set_code_from_bottom_left_crop(
        self,
        image_bytes: bytes,
        mime_type: GroqVisionImageMimeType,
        options: GroqVisionExtractOptions | None,
    ) -> str | None:
        try:
            crop = self._crop_bottom_left_set_code_zone(image_bytes)
            b64 = base64.b64encode(crop).decode("ascii")
            data_url = f"data:{mime_type};base64,{b64}"
            if len(data_url.encode("utf-8")) > MAX_BASE64_IMAGE_BYTES:
                return None
            opts = options or {}
            model = opts.get("model", DEFAULT_MODEL)
            hint = self._normalize_user_hint(opts.get("user_hint"))
            crop_user_text = (
                "Transcribe setCode from the first dark box on the bottom-left collector row, "
                "immediately left of the fraction. For SV* codes, copy every character exactly "
                "(e.g. SV5a is not SV4K)."
            )
            if hint:
                crop_user_text += (
                    " Optional hint from the user (use only if it matches the visible box): "
                    + hint
                )
            body: dict[str, Any] = {
                "model": model,
                "temperature": 0,
                "max_completion_tokens": SET_CODE_CROP_MAX_COMPLETION_TOKENS,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            'Return JSON only with key "setCode". Read only the first dark box text on the '
                            "bottom-left collector row, immediately left of the collector fraction. Prefer "
                            "literal transcription from that box over inferred set family. If a clear "
                            "3-char letter-digit-letter code is visible (e.g. M1L, M1S), output it exactly. "
                            "Scarlet/Violet Japanese subsets use SV + digit + suffix (e.g. SV5a, SV4K): read each "
                            "glyph carefully — digit 5 vs 4 and last letter **a** vs **K** are different sets. "
                            "Never output regulation letters (H, D, E) as set code. Use null only if illegible."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": crop_user_text,
                            },
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
            }
            url = f"{self._base_url}{CHAT_COMPLETIONS_PATH}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            }
            response = httpx.post(url, headers=headers, json=body, timeout=120.0)
            body_text = response.text
            if not response.is_success:
                return None
            parsed = self._parse_json_body(body_text)
            content = self._pick_assistant_content(parsed)
            if content is None or content.strip() == "":
                return None
            content_parsed = self._parse_json_body(content)
            rec = self._as_record_or_null(content_parsed)
            if rec is None:
                return None
            candidate_raw = self._read_nullable_string(rec, "setCode")
            return self._normalize_set_code_candidate(candidate_raw)
        except (RuntimeError, OSError, ValueError):
            return None

    def _crop_bottom_left_set_code_zone(self, source: bytes) -> bytes:
        buf = io.BytesIO(source)
        img = Image.open(buf)
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        if w == 0 or h == 0:
            return source
        left = 0
        # Tighter band on the bottom edge so the collector row (set box + fraction) fills more of the crop.
        top = max(0, int(h * 0.80))
        crop_w = max(1, int(w * 0.42))
        crop_h = max(1, h - top)
        cropped = img.crop((left, top, left + crop_w, top + crop_h))
        cw, ch = cropped.size
        if cw < 880 and cw > 0:
            scale = min(2.5, 880 / cw)
            new_w = max(1, int(cw * scale))
            new_h = max(1, int(ch * scale))
            cropped = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        cropped.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()

    @staticmethod
    def _normalize_set_code_candidate(value: str | None) -> str | None:
        if value is None:
            return None
        compact = re.sub(r"\s+", "", value).upper()
        if not re.match(r"^[A-Z0-9-]{2,12}$", compact):
            return None
        if re.match(r"^[A-Z]$", compact):
            return None
        if re.match(r"^[A-Z][0-9][A-Z]$", compact):
            return compact
        return compact

    @staticmethod
    def _normalize_set_code_case(value: str) -> str:
        return value.strip().upper()

    @staticmethod
    def _resolve_mime_type_from_path(file_path: str) -> GroqVisionImageMimeType:
        lower = Path(file_path).suffix.lower()
        if lower == ".png":
            return "image/png"
        if lower == ".webp":
            return "image/webp"
        return "image/jpeg"

    @staticmethod
    def _build_system_prompt() -> str:
        parts = [
            "You read Pokémon trading card photos and extract collector data and visible text.",
            "Respond with a single JSON object, no markdown.",
            'Keys: "setCode", "cardNumber", "pokemonName", "pokemonNameEnglish", "pokemonNameFrench", '
            '"cardVariantLabel", "setNameEnglish" — each string|null.',
            "setCode — WHERE TO LOOK: On the **bottom border** of the card, **left half**, scan **left-to-right** "
            "along the same row as the collector fraction (e.g. 063/065). The **set code is almost always the first "
            "token in that row inside a small dark (often black) rectangle** with **contrasting light text** "
            "(white or silver). It sits **immediately left of** the card number / fraction; do not confuse it with "
            "a regulation letter in a tiny box farther left (e.g. H, D) — that is not the set code. "
            "Do not use the big Pokémon name at the top.",
            "setCode — WHAT IT LOOKS LIKE: Short alphanumeric (M1L, M1S, SV7, SV2a, SV5a, SV4K, SWSH12, SM-P, etc.). "
            "Japanese Scarlet/Violet subsets often use **SV + one digit + suffix letter** (e.g. SV5a Triplet Beat); "
            "**SV5a and SV4K are different products** — read digit-by-digit (5 vs 4) and the last character (**a** vs **K**) "
            "from the box; do not guess from memory. "
            "Transcribe **exactly** what is inside that first dark box; normalize Latin letters in setCode to uppercase. "
            "If that box is readable, you **must** output setCode — unfamiliar patterns like M1L are still valid. "
            "null **only** if that specific box is cropped, blurred, or truly illegible.",
            "cardNumber: the **collector fraction or index** printed **just right of** the set-code box on the same "
            "bottom row (e.g. 063/065, 009/106). Exactly as printed.",
            "pokemonName: **Large species title** near the top of the artwork (Japanese / katakana as printed on JP cards). "
            "Transcribe it faithfully; null only if that text is cropped or illegible.",
            "pokemonNameEnglish: official English species name only (e.g. Gulpin, Rabsca). null if unsure.",
            "pokemonNameFrench: **exact** French Pokédex species name for that same species (e.g. Gloupti for Gulpin, "
            "Herbizarre for Ivysaur). Never use a descriptive French word or translation of a type — use the "
            "official name only. If you output pokemonNameEnglish, output the matching French dex name; "
            "null only if the species is unknown.",
            "cardVariantLabel: short subtype/rarity **as printed** on the card — e.g. ex, V, VMAX, AR, SAR, SR, RR, IR, "
            "Common/C, promo, ACE SPEC. Combine nearby symbols if needed. null if standard with no extra mark.",
            "setNameEnglish: English expansion name **only if** visible on the card (e.g. Stellar Crown). "
            "null if only Japanese or unknown.",
            "Prefer null over guessing for names and rarities. For setCode, prefer **literal transcription** of the "
            "bottom-left dark box over null when anything is visible there.",
        ]
        return " ".join(parts)

    @staticmethod
    def _normalize_user_hint(raw: Any) -> str | None:
        if not isinstance(raw, str):
            return None
        t = " ".join(raw.strip().split())
        if not t:
            return None
        return t[:500]

    @staticmethod
    def _build_user_prompt(hint: str | None = None) -> str:
        base = (
            "Extract all fields. Focus on the **bottom edge, left side**: find the **first small dark rectangular box** "
            "with light text on the same line as the card number — that text is **setCode** (e.g. M1L, SV7, SV5a). "
            "On SV* Japanese cards, transcribe the full code from the box character-by-character (5≠4, a≠K). "
            "The **cardNumber** is the fraction or number **to the right** of that box. Return JSON only."
        )
        if hint:
            base += (
                " The user provided an optional hint (Pokémon name, set code, expansion, or number—use only if "
                "consistent with what you see on the card, never override a clear reading of the image): "
                + hint
            )
        return base

    @staticmethod
    def _parse_json_body(body_text: str) -> Any:
        try:
            return json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Groq response was not valid JSON.") from exc

    def _pick_assistant_content(self, payload: Any) -> str | None:
        rec = self._as_record_or_null(payload)
        if rec is None:
            return None
        choices_unknown = rec.get("choices")
        if not isinstance(choices_unknown, list) or not choices_unknown:
            return None
        first = choices_unknown[0]
        first_record = self._as_record_or_null(first)
        if first_record is None:
            return None
        message_unknown = first_record.get("message")
        message_record = self._as_record_or_null(message_unknown)
        if message_record is None:
            return None
        content_unknown = message_record.get("content")
        if isinstance(content_unknown, str):
            return content_unknown
        return None

    def _parse_collector_result_json(self, content: str) -> GroqVisionCardCollectorResult:
        trimmed = content.strip()
        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Groq assistant content was not valid JSON.") from exc
        record = self._as_record_or_null(parsed)
        if record is None:
            raise RuntimeError("Groq assistant JSON was not an object.")

        set_code = self._read_nullable_string(record, "setCode")
        card_number = self._read_nullable_string(record, "cardNumber")
        pokemon_name = self._read_nullable_string(record, "pokemonName")
        pokemon_name_english = self._read_nullable_string(record, "pokemonNameEnglish")
        if pokemon_name_english is None and pokemon_name and self._looks_like_latin_pokemon_name(pokemon_name):
            pokemon_name_english = pokemon_name
        pokemon_name_french = self._read_nullable_string(record, "pokemonNameFrench")
        card_variant_label = self._read_nullable_string(record, "cardVariantLabel")
        set_name_english = self._read_nullable_string(record, "setNameEnglish")
        if set_name_english is not None and set_code is not None:
            set_name_english = self._strip_leading_set_code_prefix_from_set_name(set_name_english, set_code)

        split = self._split_card_collector_fraction(card_number)
        return {
            "set_code": set_code,
            "card_number": card_number,
            "card_number_numerator": split["card_number_numerator"],
            "card_number_denominator": split["card_number_denominator"],
            "pokemon_name": pokemon_name,
            "pokemon_name_english": pokemon_name_english,
            "pokemon_name_french": pokemon_name_french,
            "card_variant_label": card_variant_label,
            "set_name_english": set_name_english,
            "rarity_english": None,
        }

    @staticmethod
    def _looks_like_latin_pokemon_name(value: str) -> bool:
        trimmed = value.strip()
        if trimmed == "":
            return False
        return bool(
            re.match(
                r"^[\s'A-Za-z.\-éèêëàâäôöîïûüçÉÈÊËÀÂÄÔÖÎÏÛÜÇ0-9]+$",
                trimmed,
            )
        )

    def _build_card_number_lookup_candidates(self, card_number: str) -> list[str]:
        trimmed = card_number.strip()
        values: list[str] = []
        if trimmed:
            values.append(trimmed)
        split = self._split_card_collector_fraction(trimmed)
        num = split["card_number_numerator"]
        den = split["card_number_denominator"]
        if num is not None and den is not None:
            swapped = f"{den}/{num}"
            if swapped not in values:
                values.append(swapped)
        return values

    @staticmethod
    def _normalize_card_number(value: str | None) -> str | None:
        if value is None:
            return None
        t = value.strip()
        if t == "":
            return None
        return re.sub(r"\s+", "", t).upper()

    @staticmethod
    def _normalize_text_for_match(value: str | None) -> str:
        if value is None:
            return ""
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _pick_best_wallet_result(
        self,
        results: list[PokeWalletCard],
        collector: GroqVisionCardCollectorResult,
        hint: str | None,
    ) -> PokeWalletCard:
        wanted_set = self._normalize_set_code_case(collector["set_code"]) if collector.get("set_code") else None
        wanted_num = self._normalize_card_number(collector.get("card_number"))
        wanted_en = self._normalize_text_for_match(collector.get("pokemon_name_english"))
        wanted_printed = self._normalize_text_for_match(collector.get("pokemon_name"))
        normalized_hint = self._normalize_text_for_match(hint)

        def score(card: PokeWalletCard) -> int:
            info = card.get("card_info", {})
            if not isinstance(info, dict):
                return 0
            points = 0
            card_set = self._normalize_set_code_case(info.get("set_code", "")) if info.get("set_code") else None
            card_num = self._normalize_card_number(info.get("card_number"))
            clean_name = self._normalize_text_for_match(info.get("clean_name"))
            raw_name = self._normalize_text_for_match(info.get("name"))
            joined_name = f"{clean_name} {raw_name}".strip()
            if wanted_set is not None and card_set == wanted_set:
                points += 12
            if wanted_num is not None and card_num == wanted_num:
                points += 10
            if wanted_en and wanted_en in joined_name:
                points += 8
            if wanted_printed and wanted_printed in joined_name:
                points += 6
            if normalized_hint:
                hint_tokens = [tok for tok in normalized_hint.split() if len(tok) >= 2]
                token_hits = sum(1 for tok in hint_tokens if tok in joined_name)
                points += min(8, token_hits * 2)
                if wanted_set is None and any(tok == (card_set or "").lower() for tok in hint_tokens):
                    points += 6
                if wanted_num is None and any(tok == (card_num or "").lower() for tok in hint_tokens):
                    points += 5
            return points

        best = max(results, key=score)
        return best

    @staticmethod
    def _split_card_collector_fraction(card_number: str | None) -> dict[str, str | None]:
        if not card_number:
            return {"card_number_numerator": None, "card_number_denominator": None}
        trimmed = card_number.strip()
        m = re.match(r"^(\d+)\s*/\s*(\d+)$", trimmed)
        if m:
            return {
                "card_number_numerator": m.group(1),
                "card_number_denominator": m.group(2),
            }
        if re.match(r"^\d+$", trimmed):
            return {"card_number_numerator": trimmed, "card_number_denominator": None}
        return {"card_number_numerator": None, "card_number_denominator": None}

    @staticmethod
    def _read_nullable_string(record: dict[str, Any], key: str) -> str | None:
        value = record.get(key)
        if value is None:
            return None
        if isinstance(value, str):
            t = value.strip()
            return None if t == "" else t
        return None

    @staticmethod
    def _as_record_or_null(value: Any) -> dict[str, Any] | None:
        if value is None or not isinstance(value, dict):
            return None
        return value

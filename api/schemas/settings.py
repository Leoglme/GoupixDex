from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    margin_percent: int
    vinted_enabled: bool
    ebay_enabled: bool
    ebay_marketplace_id: str
    ebay_category_id: str | None
    #: Instance default from ``EBAY_DEFAULT_CATEGORY_ID`` (read-only); used when ``ebay_category_id`` is empty.
    ebay_default_category_id: str | None
    ebay_merchant_location_key: str | None
    ebay_fulfillment_policy_id: str | None
    ebay_payment_policy_id: str | None
    ebay_return_policy_id: str | None
    ebay_connected: bool
    ebay_listing_config_complete: bool
    ebay_oauth_configured: bool
    ebay_environment: str


class SettingsUpdate(BaseModel):
    margin_percent: int | None = Field(default=None, ge=0, le=500)
    vinted_enabled: bool | None = None
    ebay_enabled: bool | None = None
    ebay_marketplace_id: str | None = Field(default=None, max_length=32)
    ebay_category_id: str | None = Field(default=None, max_length=32)
    ebay_merchant_location_key: str | None = Field(default=None, max_length=64)
    ebay_fulfillment_policy_id: str | None = Field(default=None, max_length=32)
    ebay_payment_policy_id: str | None = Field(default=None, max_length=32)
    ebay_return_policy_id: str | None = Field(default=None, max_length=32)

/**
 * OpenCV.js source URL. It is loaded **inside the card-detector Web Worker**
 * (see `app/workers/cardDetector.worker.ts`) — never on the main thread, which
 * would freeze the phone while the ~11 MB wasm parses/instantiates.
 *
 * Self-hosted (`web/public/opencv/opencv.js`, build 4.13.0 from
 * docs.opencv.org): the CDN deletes old version folders without notice —
 * `4.10.0/opencv.js` started returning 404 (NoSuchKey) and silently killed the
 * scan engine in prod. Same-origin also avoids any CSP / CORS surprise.
 */
export const OPENCV_URL = '/opencv/opencv.js'

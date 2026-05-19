/**
 * OpenCV.js source URL. It is loaded **inside the card-detector Web Worker**
 * (see `app/workers/cardDetector.worker.ts`) — never on the main thread, which
 * would freeze the phone while the ~9 MB wasm parses/instantiates.
 *
 * Self-host to avoid any prod CSP issue with the CDN: drop `opencv.js` in
 * `web/public/opencv/` and set this to `/opencv/opencv.js`.
 */
export const OPENCV_URL = 'https://docs.opencv.org/4.10.0/opencv.js'

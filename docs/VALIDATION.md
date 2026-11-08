# Validation for 0.1.0

Tested on Windows 11, AMD Radeon RX 9070 XT and Ryzen 7 7800X3D.

## Automated checks

The local suite contains **22 passing tests**, plus the browser and packaged-application integration checks below. Hosted CI has not yet been run; an optional workflow template is supplied separately.

- Pure analysis: constant-rate streams, 1% low calculation, spike preservation, event grouping, zero-baseline comparisons, GPU evidence and missing values.
- CSV import: dominant swap-chain selection, legacy seconds, unknown-format rejection and missing GPU timing.
- Storage/API: round-trip persistence, capture ID validation, first-run empty data, export escaping, write-token enforcement, Host validation, and path traversal rejection.
- Incident windows: wait for delayed recovery frames before finalizing the marked interval.
- Browser workflow: empty state, labelled examples, navigation, report view, SVG download, comparison, mobile overflow and no page errors.

## Real frame capture

A separate pygame/Direct3D fixture rendered a moving rectangle at approximately 60 FPS with three deliberately inserted 180 ms stalls. No user's game or emulator was controlled.

After selecting the light PresentMon capture path, one 11.66-second run captured **679 presented frames** and identified **all three deliberate stutter events**. CPU, memory and Windows GPU-engine samples were received. A marked incident was persisted separately. This validates the recording path; it is not a benchmark of a commercial game or a calibrated root-cause detector.

The packaged executable independently captured **556 frames** and identified **three stutter events** in a second controlled run. It saved an 8.178-second marked incident, received GPU-engine readings and exported the SVG report.

The desktop executable launched successfully and created its native WebView2 window. Its JavaScript-to-Python bridge was tested through the actual Export report button, producing a standalone HTML file. Further platform/GPU testing is welcome. Counter availability and ETW behavior can vary across Windows versions, graphics drivers and rendering APIs.

The visual inspector reported **0 failures and 0 warnings** at 1440, 768 and 390 pixels; the resulting screenshots were reviewed. Internal critique: clarity 8/10, information consistency 9/10, layout 8/10. The capture screen intentionally starts empty; desktop capture remains the product's primary use case.

## Design

Data-terminal direction, seed 769170631. Public Sans for interface text and IBM Plex Mono for metric figures. The product's signature is a marked incident window around a frame-time spike. All sample captures and screenshots are explicitly labelled synthetic examples.

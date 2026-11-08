# Understand your project

Work through these exercises in order. Run the tests after every change.

## Trace one frame

Open `importer.py`. Find how a CSV row becomes a dictionary containing `t`, `ms`, `gpu_ms` and `cpu_ms`. Explain why a missing GPU reading must stay `None` rather than becoming zero.

Exercise: add a test that imports a row with `NA` in the GPU column.

## Calculate a metric by hand

For frame times `[10, 10, 10, 50]`, calculate average FPS as `1000*4/80 = 50`. Averaging the individual FPS values would give the wrong answer. Compare your result with `analyze` in `analysis.py`.

Exercise: add this exact example to the tests.

## Follow a stutter event

Explain the difference between a slow frame and a grouped stutter event. Locate the 150 ms grouping rule and explain why consecutive slow frames should not necessarily count as separate incidents.

Exercise: test two spikes separated by one second. They should form two events.

## Follow a button through the app

In `ui/app.js`, find the Start recording handler. It sends a JSON request to `server.py`, which validates the input and calls `CaptureManager.start`. The capture adapter starts PresentMon, reads its CSV stream, and periodically exposes a snapshot to the UI.

Exercise: write down which thread reads frames, which samples sensors, and which serves UI requests. Explain why a lock is used around shared state.

## Explain the limits

Be able to explain why a correlation is not a cause, why a network probe is not game-server ping, why two different game scenes are not a fair comparison, and why examples must be labelled.

Exercise: write a new finding rule on paper, including its required data, thresholds, counterexamples and tests, before changing the code.

## Make a small independent contribution

Choose one: improve an empty-state sentence, add a CSV fixture, improve chart keyboard accessibility, or add another export field. Create a branch, write the change and a meaningful test, and explain it in a pull request.

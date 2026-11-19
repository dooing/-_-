# Step-by-Step Screenshot Animation (for PPT)

This tool turns screenshots into **slides that animate one step at a time each time you press the spacebar**.
At each step, the camera zooms into the region it is explaining, and the rest of the screen dims while a highlight box and an explanation card appear.
After the animation plays, it holds on that frame, and pressing the spacebar plays the next step's animation.

Result: a PowerPoint file (.pptx) with one video per step, set to play automatically. You can copy the slides and paste them into an existing presentation.

## Files

* `walkthrough.py`: Animation engine (normally no need to modify)
* `demo_deck.py`: Example deck. Copy it and change only the image, region, and explanation
* `pick_region.py`: Tool that gets pixel coordinates when you drag over a region of a screenshot
* `make_sample_images.py`: Generates the 2 fake screenshots used in the demo
* `output/DemoDeck.pptx`: Rendered demo PPT

## Installation

Python 3.11 or 3.12 is recommended.

```bash
pip install -r requirements.txt
```

The versions are pinned for a reason (confirmed as of 2026-11).

* `manim` 0.22 is not compatible with `manim-slides` 5.7, so you get a `write_to_movie` error. Use 0.21.0.
* With Pillow 12 or later, manim 0.21 raises an `Invalid mode for data type` error when rendering images. Use `pillow<12`.

You do not need to install LaTeX or FFmpeg separately (manim uses the built-in PyAV).

## Usage

1. **Prepare screenshots**: Put the screen images you will explain into a folder such as `images/`.

2. **Get region coordinates**: Drag over the region to highlight, and the coordinates are printed in a form you can paste straight into a Step.
   ```bash
   python pick_region.py images/my_screen.png
   ```

3. **Write a deck**: Copy `demo_deck.py` to create `my_deck.py`, then edit the class name and `STEPS`.
   ```python
   from walkthrough import Step, Walkthrough

   class MyDeck(Walkthrough):
       THEME = "dark"                      # or "light"
       EYEBROW = "METHOD OVERVIEW"         # small uppercase text above the cover title
       TITLE = "New Analysis Method\nStep-by-Step Overview" # \n starts a new line
       SUBTITLE = "Cover subtitle"
       HEADER = "Text shown at the top left"
       STEPS = [
           Step("images/screen1.png", (18, 77, 369, 484), "Load data",
                "Wrap in **double asterisks** to show it in bold with the highlight color."),
           Step("images/screen1.png", (387, 77, 1782, 682), "Results graph",
                "If you don't want to zoom, set zoom=False.", zoom=False),
       ]
   ```

4. **Render** (run inside this folder)
   ```bash
   manim-slides render -ql my_deck.py MyDeck                   # quick check (low resolution)
   manim-slides render -qh --frame_rate 30 my_deck.py MyDeck   # final (1080p)
   ```

5. **Preview**: Opens a window that advances with the spacebar.
   ```bash
   manim-slides present MyDeck
   ```

6. **Convert to PPT**
   ```bash
   manim-slides convert --to=pptx MyDeck output/MyDeck.pptx
   ```

## Using it in PPT

* The slide size is the standard 16:9 (13.33 x 7.5 in). Copy the slides and paste them into an existing presentation as is.
* Each slide contains that step's video, set to play automatically. During the slide show, pressing the spacebar moves to the next slide and plays the next animation.
* The explanation text for each step is included in the speaker notes.

## Options

Deck (class attributes)

* `THEME`: `"dark"` or `"light"`. If your PPT background is light, use `"light"`
* `EYEBROW`, `TITLE`, `SUBTITLE`: cover text
* `HEADER`: small text at the top left during the steps (defaults to TITLE)
* `SHOW_RECAP`, `RECAP_TITLE`: whether to show the final summary slide, and its title
* `MOVE_TIME`: camera move time in seconds (default 1.6)
* `MAX_UPSCALE`: maximum zoom factor (default 2.0). Raise it if small regions look too small, lower it if they get blurry
* `FONT`: font name. If unset, an installed Korean font is chosen automatically (Pretendard, Noto Sans KR, Malgun Gothic, ...)

Step

* `image`: image path (relative to the deck file)
* `region`: `(x0, y0, x1, y1)`, image pixel coordinates (top left is 0, 0)
* `title`, `body`: card title and body. Line breaks are automatic, and `**text**` gets highlighted
* `zoom`: `True` (default) zooms into the region; `False` keeps the whole screen and only highlights the region
* `layout`: `"auto"` (default), `"side"` (card on the right), `"bottom"` (card at the bottom). auto picks the layout that shows the region larger
* `notes`: speaker notes (if omitted, title + body)

## Troubleshooting

* Korean shows as boxes: specify a font installed on your PC, such as `FONT = "Malgun Gothic"`.
* Screenshots are blurry: use the original captures at a high resolution (at least the monitor's native resolution), and adjust `MAX_UPSCALE` to 1.5 or so.
* Rendering is slow: check layout and text with `-ql` first, and render with `-qh` only at the end.

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

prompt = """
Transform the reference image into a high-detail coloring book page made of pure black ink line art only. The output must be ONLY crisp black outlines on a completely blank white page. No color AT ALL, no shading, and no grayscale. Preserve and emphasize all intricate details of the clothing, garments, and accessories from the reference image, including precise seams, fabric folds, texture lines, buttons, belts, buckles, bag straps, and graphic prints. All content should be rendered as clean, refined, and continuous black line drawings with crisp, consistent stroke weight. All shapes must be unfilled, hollow, and clearly defined with fully closed outlines suitable for precision coloring. Isolate the main subject(s) from the reference image and place them centered on an empty white page with margins. The background must remain 100% blank white with zero detail or decoration.
"""


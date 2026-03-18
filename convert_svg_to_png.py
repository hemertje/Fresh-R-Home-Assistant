#!/usr/bin/env python3
"""Convert Fresh-R SVG logo to PNG for Home Assistant brand icon."""

import cairosvg
import sys

def convert_svg_to_png(svg_path, png_path, width=256, height=256):
    """Convert SVG to PNG with specified dimensions."""
    try:
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_path,
            output_width=width,
            output_height=height,
            background_color='white'
        )
        print(f"✅ Successfully converted {svg_path} to {png_path}")
        print(f"   Size: {width}x{height}px")
        return True
    except Exception as e:
        print(f"❌ Error converting SVG: {e}")
        return False

if __name__ == "__main__":
    svg_file = "custom_components/fresh_r/icons/fresh-r-simple.svg"
    png_file = "custom_components/fresh_r/icon.png"
    
    print("🎨 Converting Fresh-R SVG to PNG...")
    success = convert_svg_to_png(svg_file, png_file, 256, 256)
    
    if success:
        print("🎉 Icon ready for Home Assistant!")
        sys.exit(0)
    else:
        print("⚠️  Conversion failed - trying alternative method...")
        sys.exit(1)

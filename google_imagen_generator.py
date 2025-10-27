"""
Google Gemini Image Generation Module (Nano Banana)

This module provides functionality to generate images from text prompts
using Google's Gemini 2.5 Flash Image model (aka "Nano Banana").

This uses the NEW google-genai SDK and the same credentials as Gemini chat models.
"""

import os
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import google-genai (the NEW SDK)
try:
    from google import genai
    from google.genai import types
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("Warning: google-genai not installed. Install it with: pip install google-genai")

# Global client
_client = None


def get_client():
    """Get or create Google GenAI client"""
    global _client

    if _client is not None:
        return _client

    if not GOOGLE_AVAILABLE:
        raise ImportError("google-genai is not installed. Install it with: pip install google-genai")

    # Get API key from environment (same as Gemini!)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment. Please set it in .env file")

    _client = genai.Client(api_key=api_key)
    print("✓ Google GenAI client configured (using Nano Banana model)")
    return _client


def generate_image_from_text_prompt(
    prompt: str,
    num_images: int = 1,
    width: int = 512,
    height: int = 512,
    seed: int = None
) -> Image.Image:
    """
    Generate an image from a text prompt using Google Gemini 2.5 Flash Image (Nano Banana).

    This uses the same credentials as your Gemini chat models!

    Args:
        prompt (str): The text prompt describing the image to generate
        num_images (int): Number of images to generate (default: 1, only first is returned)
        width (int): Width of the generated image in pixels (default: 512)
        height (int): Height of the generated image in pixels (default: 512)
        seed (int): Random seed for reproducibility (default: None - not supported yet)

    Returns:
        PIL.Image.Image: The generated image

    Example:
        >>> image = generate_image_from_text_prompt(
        ...     prompt="a serene mountain landscape at sunset",
        ...     width=512,
        ...     height=512
        ... )
        >>> image.save("output.png")
    """

    # Get the client
    client = get_client()

    print(f"Generating image with Nano Banana (Gemini 2.5 Flash Image)...")
    print(f"  Prompt: {prompt}")
    print(f"  Target size: {width}x{height}")
    if seed is not None:
        print(f"  Note: Seed parameter not yet supported by Gemini image generation")

    try:
        # Generate image using Gemini 2.5 Flash Image (Nano Banana)
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
        )

        # Extract image from response
        image = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                # Got the image data!
                image = Image.open(BytesIO(part.inline_data.data))
                break

        if image is None:
            raise Exception("No image was generated in the response")

        # Resize to requested dimensions if needed
        if image.size != (width, height):
            print(f"  Resizing from {image.size} to {width}x{height}")
            image = image.resize((width, height), Image.Resampling.LANCZOS)

        print("✓ Image generation complete!")
        return image

    except Exception as e:
        print(f"✗ Error generating image with Nano Banana: {e}")
        import traceback
        traceback.print_exc()
        raise


# Example usage
if __name__ == "__main__":
    # Test the function
    test_prompt = "a majestic dragon soaring over a medieval castle at golden hour, cinematic lighting, highly detailed"

    print("Testing Google Imagen image generation...")
    try:
        image = generate_image_from_text_prompt(
            prompt=test_prompt,
            width=512,
            height=512
        )

        # Save the test image
        output_path = "test_google_generation.png"
        image.save(output_path)
        print(f"Test image saved to: {output_path}")
    except Exception as e:
        print(f"Test failed: {e}")

"""
FLUX.1-Kontext-dev Image Generation Module

This module provides functionality to generate images from text prompts
using the FLUX.1-Kontext-dev model from Black Forest Labs.
"""

import torch
from diffusers import FluxPipeline
from PIL import Image
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global variable to hold the pipeline
_pipeline = None

def load_model():
    """
    Load the FLUX.1-Kontext-dev model pipeline.
    This function initializes the model only once and caches it.
    """
    global _pipeline
    
    if _pipeline is None:
        print("Loading FLUX.1-Kontext-dev model...")
        
        # Check if CUDA is available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        # Get HuggingFace token from environment
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN not found in environment. Please set it in .env file")

        # Load the pipeline with authentication token
        _pipeline = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-Kontext-dev",
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            token=hf_token
        )
        
        _pipeline = _pipeline.to(device)
        
        # Enable memory optimizations if on GPU
        if device == "cuda":
            # Enable attention slicing for memory efficiency
            _pipeline.enable_attention_slicing()
            
            # Try to enable xformers if available
            try:
                _pipeline.enable_xformers_memory_efficient_attention()
                print("xformers memory efficient attention enabled")
            except Exception as e:
                print(f"xformers not available: {e}")
        
        print("Model loaded successfully!")
    
    return _pipeline

def generate_image_from_text_prompt(
    prompt: str,
    num_inference_steps: int = 28,
    guidance_scale: float = 3.5,
    width: int = 512,
    height: int = 512,
    seed: int = None
) -> Image.Image:
    """
    Generate an image from a text prompt using FLUX.1-Kontext-dev.
    
    Args:
        prompt (str): The text prompt describing the image to generate
        num_inference_steps (int): Number of denoising steps (default: 28)
                                   Higher values = better quality but slower
        guidance_scale (float): How closely to follow the prompt (default: 3.5)
                               Higher values = stricter adherence to prompt
        width (int): Width of the generated image in pixels (default: 512)
        height (int): Height of the generated image in pixels (default: 512)
        seed (int): Random seed for reproducibility (default: None for random)
    
    Returns:
        PIL.Image.Image: The generated image
    
    Example:
        >>> image = generate_image_from_text_prompt(
        ...     prompt="a serene mountain landscape at sunset",
        ...     num_inference_steps=30,
        ...     guidance_scale=4.0
        ... )
        >>> image.save("output.png")
    """
    
    # Load the model if not already loaded
    pipeline = load_model()
    
    # Set up the generator for reproducibility if seed is provided
    generator = None
    if seed is not None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        generator = torch.Generator(device=device).manual_seed(seed)
    
    print(f"Generating image...")
    print(f"  Prompt: {prompt}")
    print(f"  Steps: {num_inference_steps}")
    print(f"  Guidance: {guidance_scale}")
    print(f"  Size: {width}x{height}")
    if seed is not None:
        print(f"  Seed: {seed}")
    
    # Generate the image
    result = pipeline(
        prompt=prompt,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        width=width,
        height=height,
        generator=generator
    )
    
    # Extract the image from the result
    image = result.images[0]
    
    print("Image generation complete!")
    
    return image

# Example usage
if __name__ == "__main__":
    # Test the function
    test_prompt = "a majestic dragon soaring over a medieval castle at golden hour, cinematic lighting, highly detailed"
    
    print("Testing FLUX.1-Kontext-dev image generation...")
    image = generate_image_from_text_prompt(
        prompt=test_prompt,
        num_inference_steps=28,
        guidance_scale=3.5,
        width=1024,
        height=1024,
        seed=42
    )
    
    # Save the test image
    output_path = "test_generation.png"
    image.save(output_path)
    print(f"Test image saved to: {output_path}")
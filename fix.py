#!/usr/bin/env python3
"""
Fix video modal display to show videos with correct aspect ratio,
not stretched to full screen.
"""

from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

def fix_civitai_video_modal():
    """Update the civitai index.html to improve video modal display."""
    
    civitai_html = SCRIPT_DIR / 'civitai' / 'index.html'
    
    if not civitai_html.exists():
        print(f"❌ {civitai_html} not found")
        return False
    
    try:
        with open(civitai_html, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find and replace the modal-media CSS
        old_css = """        .modal-media {
            max-width: 100%;
            max-height: 85vh;
            object-fit: contain;
        }"""
        
        new_css = """        .modal-media {
            max-width: 90vw;
            max-height: 80vh;
            width: auto;
            height: auto;
            object-fit: contain;
        }"""
        
        if old_css in content:
            content = content.replace(old_css, new_css)
            
            with open(civitai_html, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Fixed video modal display!")
            print("   Videos will now show with correct aspect ratio")
            print("   (not stretched to full screen)")
            return True
        else:
            print("⚠️  Could not find the exact CSS to replace")
            print("   Modal CSS might already be updated or different")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("🎬 Fixing Video Modal Display")
    print("=" * 60)
    print()
    
    if fix_civitai_video_modal():
        print()
        print("=" * 60)
        print("✅ Done! Restart server to see changes:")
        print("   python server.py")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("⚠️  Fix not applied. Manual update may be needed.")
        print("=" * 60)

if __name__ == "__main__":
    main()
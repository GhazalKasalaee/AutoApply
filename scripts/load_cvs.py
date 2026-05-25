"""
One-time script: load your 4 CV text files into ChromaDB.
 
To update after editing your CVs:
    python scripts/load_cvs.py --force
"""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.cv_selector import load_cvs_into_chromadb, CVS_DIR

 
def main():
    force = "--force" in sys.argv
 
    print("=" * 60)
    print("  AutoApply AI — CV Loader (ChromaDB)")
    print("=" * 60)
    print(f"\n  CV directory: {CVS_DIR}")
    print(f"  Force reload: {force}\n")
 
    # Check files exist
    expected = ["cv_mle.txt", "cv_genai.txt", "cv_research.txt", "cv_architect.txt"]
    missing = [f for f in expected if not (CVS_DIR / f).exists()]
 
    if missing:
        print("  ❌ Missing CV files:")
        for f in missing:
            print(f"     - {CVS_DIR / f}")
        print(f"\n  Create these files first. Each should contain the plain text")
        print(f"  version of your targeted CV (copy from your LaTeX-compiled PDF).")
        print(f"\n  Example: copy the text content of your own resume export into data/cvs/cv_mle.txt")
        print(f"  into data/cvs/cv_mle.txt")
        sys.exit(1)
 
    # Load into ChromaDB
    load_cvs_into_chromadb(force_reload=force)
 
    print("\n  ✅ Done! CVs are now searchable in ChromaDB.")
    print("  Run: python scripts/day3_test.py  to test CV selection")
 
 
if __name__ == "__main__":
    main()
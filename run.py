"""Developer launcher; the portable Windows release does not need Python."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'src'))
from laglens.app import main

if __name__ == '__main__':
    main()

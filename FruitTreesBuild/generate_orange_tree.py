"""Edit configs/orange_tree.json, then run this fixed script without arguments."""
import sys
from scripts.tree_launcher import ROOT, main as launch_tree


def main(argv=None):
    return launch_tree(argv, default_config=ROOT / 'configs/orange_tree.json', expected_fruit='orange')


if __name__ == '__main__':
    sys.exit(main())

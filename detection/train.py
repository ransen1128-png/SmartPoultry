"""Train a separate localization candidate; never replace the age checkpoint."""
from pathlib import Path
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int, default=100)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    for split in ('train', 'val', 'test'):
        images = list((root / 'dataset' / 'images' / split).glob('*'))
        images = [p for p in images if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}]
        if not images:
            parser.error(f'No annotated images in {split}; follow detection/README.md first.')
        for image in images:
            label = root / 'dataset' / 'labels' / split / (image.stem + '.txt')
            if not label.is_file():
                parser.error(f'Missing reviewed annotation: {label}')
            for line in label.read_text().splitlines():
                values = line.split()
                try:
                    cls, x, y, w, h = map(float, values)
                    valid = (cls in (0, 1) and 0 < w <= 1 and 0 < h <= 1
                             and 0 <= x - w / 2 <= x + w / 2 <= 1
                             and 0 <= y - h / 2 <= y + h / 2 <= 1)
                except ValueError:
                    valid = False
                if not valid:
                    parser.error(f'Invalid YOLO box in {label}: {line}')
    from ultralytics import YOLO
    # Write an absolute dataset root to avoid library-dependent path resolution.
    config = root / 'dataset.generated.yaml'
    config.write_text(f'path: { (root / "dataset").as_posix() }\n'
                      'train: images/train\nval: images/val\ntest: images/test\n'
                      'names:\n  0: leg\n  1: spur\n')
    model = YOLO('yolo11n.pt')
    model.train(data=str(config), epochs=args.epochs, imgsz=960,
                project=str(root / 'runs'), name='leg_spur', exist_ok=False)
    YOLO(str(model.trainer.best)).val(data=str(config), split='test', imgsz=960)


if __name__ == '__main__':
    main()

"""Build the static website index from output/image without running any API."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.avif'}


def build_data(root=ROOT):
    root = Path(root)
    image_root = root / 'output/image'
    previous = root / 'web/data.json'
    old = json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else {'brands': []}
    old_brands = {brand['id']: brand for brand in old['brands']}
    brands = []
    if not image_root.is_dir():
        raise ValueError(f'Missing image directory: {image_root}')

    def folders(folder):
        return sorted(path for path in folder.iterdir() if path.is_dir())

    def picture(path, alt, **extra):
        return {'src': '../' + path.relative_to(root).as_posix(), 'alt': alt, **extra}

    for brand in folders(image_root):
        old_brand = old_brands.get(brand.name, {})
        old_looks = {look['id']: look for look in old_brand.get('looks', [])}
        looks = []
        for season in folders(brand):
            for folder in folders(season):
                originals = [path for path in folder.glob('original.*') if path.suffix.lower() in EXTENSIONS and path.is_file()]
                if len(originals) != 1:
                    raise ValueError(f'Expected one original image: {folder}')
                look_id = f'{season.name}-{folder.name}'
                old_look = old_looks.get(look_id, {})
                name = old_look.get('name', f'{season.name} / {folder.name.replace("look-", "Look ")}')
                old_images = {image['src']: image for image in old_look.get('linearts', [])}
                linearts = []
                lineart_root = folder / 'linearts'
                if lineart_root.is_dir():
                    for model in folders(lineart_root):
                        for version in sorted(model.iterdir()):
                            if not version.is_file() or version.suffix.lower() not in EXTENSIONS:
                                continue
                            image = picture(version, f'{name} / {model.name} / {version.stem}',
                                            name=f'{model.name} / {version.stem}', model=model.name, version=version.stem)
                            image.update({key: value for key, value in old_images.get(image['src'], {}).items()
                                          if key in {'name', 'alt'}})
                            linearts.append(image)
                original = picture(originals[0], old_look.get('original', {}).get('alt', f'{name} 原始圖片'))
                looks.append({'id': look_id, 'season': season.name, 'name': name,
                              'original': original, 'linearts': linearts})
        brands.append({'id': brand.name, 'name': old_brand.get('name', brand.name.title()), 'looks': looks})
    return {'brands': brands}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if the committed index is out of date')
    args = parser.parse_args()
    data = build_data()
    target = ROOT / 'web/data.json'
    if args.check:
        if not target.exists() or json.loads(target.read_text(encoding='utf-8')) != data:
            parser.exit(1, 'web/data.json is out of date; run scripts/update_web_data.py\n')
    else:
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(target)
    looks = [look for brand in data['brands'] for look in brand['looks']]
    print(f'Index verified: {len(looks)} Looks, {sum(len(look["linearts"]) for look in looks)} linearts')


if __name__ == '__main__':
    main()

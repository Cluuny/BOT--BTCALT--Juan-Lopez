# analyze_imports.py
import os
import re
from pathlib import Path


def safe_read_file(filepath):
    encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def find_imports(directory):
    imports = set()
    py_files = list(Path(directory).rglob("*.py"))

    for py_file in py_files:
        content = safe_read_file(py_file)
        if content:
            # Buscar imports
            import_matches = re.findall(r'^import\s+(\S+)', content, re.MULTILINE)
            from_matches = re.findall(r'^from\s+(\S+)\s+import', content, re.MULTILINE)

            for match in import_matches + from_matches:
                # Extraer el primer componente del import
                base_pkg = match.split('.')[0]
                if not base_pkg.startswith('_'):
                    imports.add(base_pkg)

    return sorted(imports)


if __name__ == "__main__":
    project_imports = find_imports('.')
    with open('requirements.in', 'w', encoding='utf-8') as f:
        for imp in project_imports:
            f.write(f"{imp}\n")
    print("requirements.in generado con éxito!")
    print("Imports encontrados:", project_imports)
import subprocess
import sys


def test_api_does_not_import_training_frameworks():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import atlas.api; "
            "assert 'torch' not in sys.modules; assert 'mlflow' not in sys.modules; "
            "assert 'duckdb' not in sys.modules",
        ],
        check=True,
    )

import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

pytest.skip("Demonstration script not for automated testing", allow_module_level=True)


"""P3 smoke runner; P5 can call this from eval/smoke_test.py after review."""
import unittest
from ui.tests.test_workbench import WorkbenchTests


def main():
    suite = unittest.TestSuite([WorkbenchTests("test_native_pages_and_real_service_mock_examples")])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()

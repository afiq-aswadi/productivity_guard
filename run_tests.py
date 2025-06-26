#!/usr/bin/env python3
"""
Test runner for ProductivityGuard tests.
"""

import os
import sys
import unittest
import coverage

def run_tests_with_coverage():
    """Run tests with coverage reporting."""
    # Start coverage
    cov = coverage.Coverage(source=['productivity_guard'])
    cov.start()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Stop coverage and report
    cov.stop()
    cov.save()
    
    print("\n\nCoverage Report:")
    print("=" * 70)
    cov.report()
    
    # Generate HTML coverage report
    html_dir = os.path.join(start_dir, 'htmlcov')
    cov.html_report(directory=html_dir)
    print(f"\nDetailed HTML coverage report generated in: {html_dir}")
    
    return result.wasSuccessful()

def run_tests_simple():
    """Run tests without coverage (if coverage module not available)."""
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    try:
        success = run_tests_with_coverage()
    except ImportError:
        print("Coverage module not found. Running tests without coverage...")
        print("Install with: pip install coverage")
        print()
        success = run_tests_simple()
    
    sys.exit(0 if success else 1)
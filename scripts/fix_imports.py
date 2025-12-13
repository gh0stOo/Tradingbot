#!/usr/bin/env python3
"""Script to fix all relative imports to absolute imports"""

import os
import re
from pathlib import Path

# Define the mappings for module conversions
MODULE_MAPPINGS = {
    'data': ['database', 'data_collector', 'position_tracker'],
    'trading': ['indicators', 'regime_detector', 'candlestick_patterns', 'strategies',
                'risk_manager', 'order_manager', 'market_data', 'btc_tracker',
                'correlation_filter', 'portfolio_heat', 'position_manager',
                'slippage_model', 'indicator_cache'],
    'ml': ['genetic_optimizer', 'backtest_runner', 'parameter_scheduler',
           'training_scheduler', 'weight_optimizer', 'signal_predictor',
           'regime_classifier'],
    'integrations': ['bybit', 'notion', 'rate_limiter'],
    'utils': ['exceptions', 'retry', 'config_loader', 'logger'],
    'monitoring': ['health_check', 'alerting'],
    'backtesting': ['backtest_engine', 'walk_forward'],
    'dashboard': ['bot_state_manager', 'stats_calculator', 'routes'],
    'api': ['routes', 'server']
}

def fix_relative_imports(file_path, module_name):
    """Fix relative imports in a single file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Pattern for relative imports (but not __init__.py package exports)
    # We want to catch "from .something import" but be careful with __init__ files

    # Skip __init__.py files that use relative imports for package exports
    if file_path.endswith('__init__.py'):
        # Check if it's a package export file (typically short and simple)
        lines = content.split('\n')
        non_comment_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        if len(non_comment_lines) < 10:  # Likely a package export file
            return 0

    # Fix relative imports from current module
    # Pattern: from .module import X -> from module_name.module import X
    for module in MODULE_MAPPINGS.get(module_name, []):
        # from .module import X
        pattern = rf'from \.{module} import'
        replacement = f'from {module_name}.{module} import'
        content = re.sub(pattern, replacement, content)

        # from . import X (less common)
        pattern = rf'from \. import'
        replacement = f'from {module_name} import'
        content = re.sub(pattern, replacement, content)

    # Write back if changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return 1
    return 0

def main():
    """Main function"""
    src_path = Path('C:/OpenCode-Infrastructure/Projects/Tradingbot/src')

    total_fixed = 0

    # Iterate through all Python files
    for module_name, modules in MODULE_MAPPINGS.items():
        module_path = src_path / module_name

        if not module_path.exists():
            continue

        # Process all Python files in this module
        for py_file in module_path.glob('*.py'):
            if py_file.name == '__pycache__':
                continue

            fixed = fix_relative_imports(str(py_file), module_name)
            if fixed:
                print(f"[FIXED] {py_file.name}")
                total_fixed += 1
            else:
                print(f"[SKIPPED] {py_file.name}")

    print(f"\n[SUCCESS] Total files fixed: {total_fixed}")

if __name__ == '__main__':
    main()

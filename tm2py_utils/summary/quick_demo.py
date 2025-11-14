#!/usr/bin/env python3
"""
Quick Demo Script for CTRAMP Summary System

This script tests the environment and creates sample data in one go,
without requiring multiple terminal commands or conda activation.
"""

def test_imports():
    """Test that all required packages are available."""
    print("Testing imports...")
    
    try:
        import pandas as pd
        print("  ✓ pandas")
        
        import numpy as np
        print("  ✓ numpy")
        
        import pydantic
        print("  ✓ pydantic")
        
        import yaml
        print("  ✓ yaml")
        
        import activitysim
        print("  ✓ activitysim")
        
        from pathlib import Path
        print("  ✓ pathlib")
        
        from enum import IntEnum
        print("  ✓ enum")
        
        return True
        
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False


def quick_demo():
    """Run a quick demonstration of the system."""
    print("\nCTRAMP Summary System Quick Demo")
    print("=" * 40)
    
    # Test environment
    if not test_imports():
        print("❌ Environment test failed")
        return False
    
    print("\n✅ All imports successful!")
    
    # Create a minimal demo dataset
    try:
        import pandas as pd
        import numpy as np
        from pathlib import Path
        
        print("\nCreating sample data...")
        
        # Simple household data
        households = pd.DataFrame({
            'hh_id': [1, 2, 3, 4, 5],
            'vehicles': [0, 1, 2, 1, 3],
            'income': [1, 2, 3, 4, 2],
            'home_mgra': [100, 200, 300, 400, 500],
            'hhsize': [1, 2, 4, 3, 5],
            'workers': [0, 1, 2, 2, 2],
            'HHT': [1, 2, 3, 2, 3],
            'BLD': [1, 2, 1, 3, 2],
            'TYPE': [1, 1, 2, 1, 2]
        })
        
        print(f"  ✓ Created {len(households)} sample households")
        
        # Simple summary
        auto_summary = households.groupby('vehicles').size().reset_index(name='count')
        auto_summary['share'] = auto_summary['count'] / auto_summary['count'].sum() * 100
        
        print("\nSample Auto Ownership Summary:")
        print(auto_summary.round(1))
        
        # Test data validation
        try:
            from ctramp_models import CTRAMPHousehold, validate_dataframe_against_model
        except ImportError:
            print("  ⚠ ctramp_models not found - validation skipped")
            return True
        
        print(f"\nTesting data validation...")
        errors = validate_dataframe_against_model(households, CTRAMPHousehold)
        
        if not errors:
            print("  ✓ Data validation passed")
        else:
            print("  ⚠ Validation issues found:")
            for error in errors[:3]:  # Show first 3 errors
                print(f"    - {error}")
        
        return True
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return False


def show_usage():
    """Show usage instructions for the full system."""
    print(f"\n🎯 CTRAMP Summary System Usage")
    print(f"=" * 35)
    
    print(f"\n1. Test the system:")
    print(f"   python quick_demo.py")
    
    print(f"\n2. Create test data:")
    print(f"   python validation/free_parking_analysis.py --create-test-data")
    
    print(f"\n3. Run focused analysis:")
    print(f"   python validation/analyze_real_data.py")
    
    print(f"\n4. Run comprehensive summaries:")
    print(f"   python run_all_summaries.py --config config_template.yaml")
    
    print(f"\n4. View results with SimWrapper:")
    print(f"   cd output_directory")
    print(f"   python launch_simwrapper.py")
    
    print(f"\n📚 Key Files:")
    print(f"   - run_all_summaries.py: Comprehensive summary generator")
    print(f"   - validation/: Focused analysis scripts")
    print(f"   - ctramp_models.py: Data validation models") 
    print(f"   - config_template.yaml: Configuration template")
    print(f"   - simwrapper_demo/: Dashboard examples")


if __name__ == "__main__":
    success = quick_demo()
    
    if success:
        show_usage()
        print(f"\n✅ Quick demo completed successfully!")
        print(f"\nThe CTRAMP summary system is ready for use with:")
        print(f"• Multiple model run comparison")
        print(f"• Survey vs model validation")  
        print(f"• Standardized summary generation")
        print(f"• Interactive SimWrapper visualization")
    else:
        print(f"\n❌ Demo failed - check environment setup")
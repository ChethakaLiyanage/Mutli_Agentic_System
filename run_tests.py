import sys
import os

# Add the backend directory to the path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("Running Retrieval Agent Tests...")
print("=" * 40)

# Test the updated retrieval agent tests
try:
    from tests.test_retrieval_agent import (
        test_claim_submission_success,
        test_claim_submission_policy_not_found,
        test_claim_status_success,
        test_claim_status_missing_identifier,
        test_wrong_user_cannot_retrieve_policy
    )

    test_claim_submission_success()
    print("✓ test_claim_submission_success passed")

    test_claim_submission_policy_not_found()
    print("✓ test_claim_submission_policy_not_found passed")

    test_claim_status_success()
    print("✓ test_claim_status_success passed")

    test_claim_status_missing_identifier()
    print("✓ test_claim_status_missing_identifier passed")

    test_wrong_user_cannot_retrieve_policy()
    print("✓ test_wrong_user_cannot_retrieve_policy passed")

    print("\n🎉 All Retrieval Agent tests passed!")

except Exception as e:
    print(f"❌ Error running tests: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
try:
    os.remove('run_tests.py')
except:
    pass
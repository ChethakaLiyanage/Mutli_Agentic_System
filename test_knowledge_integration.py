import sys
import os

# Add the backend directory to the path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("Testing Knowledge Retrieval Integration...")
print("=" * 50)

# Test 1: Check that we can import the knowledge retriever
try:
    from app.retrieval.knowledge_retriever import KnowledgeRetriever
    print("SUCCESS: Successfully imported KnowledgeRetriever")
except Exception as e:
    print(f"ERROR: Failed to import KnowledgeRetriever: {e}")

# Test 2: Check that we can import the updated service
try:
    from app.retrieval.service import RetrievalService
    from app.retrieval.repository import RetrievalRepository
    from app.retrieval.knowledge_retriever import KnowledgeRetriever
    print("SUCCESS: Successfully imported updated service and dependencies")
except Exception as e:
    print(f"ERROR: Failed to import updated service: {e}")

# Test 3: Check that service now accepts knowledge_retriever in constructor
try:
    from app.retrieval.service import RetrievalService
    import inspect

    sig = inspect.signature(RetrievalService.__init__)
    params = list(sig.parameters.keys())

    if 'knowledge_retriever' in params:
        print("SUCCESS: Service constructor accepts knowledge_retriever parameter")
    else:
        print("ERROR: Service constructor missing knowledge_retriever parameter")

    # Check that it still accepts repository
    if 'repository' in params:
        print("SUCCESS: Service constructor still accepts repository parameter")
    else:
        print("ERROR: Service constructor missing repository parameter")

except Exception as e:
    print(f"ERROR: Failed to check service constructor: {e}")

# Test 4: Check that we can see the knowledge retrieval methods in service
try:
    from app.retrieval.service import RetrievalService
    service_methods = [method for method in dir(RetrievalService) if not method.startswith('_')]
    expected_methods = ['retrieve', '_handle_knowledge_retrieval']

    for method in expected_methods:
        if method in service_methods:
            print(f"SUCCESS: Service method {method} found")
        else:
            print(f"ERROR: Service method {method} missing")

except Exception as e:
    print(f"ERROR: Failed to check service methods: {e}")

# Test 5: Check that we can see the knowledge evidence import in service
try:
    service_path = os.path.join(os.path.dirname(__file__), 'backend', 'app', 'retrieval', 'service.py')
    with open(service_path, 'r') as f:
        content = f.read()

    if 'KnowledgeEvidence' in content:
        print("SUCCESS: KnowledgeEvidence imported in service.py")
    else:
        print("ERROR: KnowledgeEvidence missing from service.py imports")

    if 'from app.retrieval.knowledge_retriever import KnowledgeRetriever' in content:
        print("SUCCESS: KnowledgeRetriever imported in service.py")
    else:
        print("ERROR: KnowledgeRetriever missing from service.py imports")

except Exception as e:
    print(f"ERROR: Failed to check service imports: {e}")

print("=" * 50)
print("Knowledge Retrieval Integration Test Complete!")
print()
print("Summary of what was implemented:")
print("1. KnowledgeRetriever class in knowledge_retriever.py")
print("   - Ready for vector search implementation with Supabase + pgvector")
print("   - Query embedding creation placeholder")
print("   - Proper KnowledgeEvidence return format")
print()
print("2. Updated service.py")
print("   - Accepts KnowledgeRetriever in constructor")
print("   - Routes required_documents_question and general_information to knowledge retrieval")
print("   - Adds optional knowledge retrieval to claim_submission, policy_question, coverage_question")
print("   - Builds contextual queries based on request data")
print("   - Returns KnowledgeEvidence objects in retrieval results")
print()
print("Ready for Step: Connect to actual Supabase + pgvector implementation")
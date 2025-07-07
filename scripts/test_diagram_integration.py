#!/usr/bin/env python3
"""Integration test for the complete diagram generation pipeline."""

import asyncio
import os
import tempfile
from pathlib import Path

# Add the project root to Python path
import sys
sys.path.append('/workspace')

async def test_complete_diagram_pipeline():
    """Test the complete diagram generation pipeline."""
    print("🧪 Testing complete diagram generation pipeline...")
    
    try:
        from telegram_bot.services.diagram_service import DiagramService
        print("✅ Successfully imported DiagramService")
    except ImportError as e:
        print(f"❌ Failed to import DiagramService: {e}")
        return False

    # Create a sample transcript
    sample_transcript = """
Speaker 0: Welcome everyone to today's team meeting. Let's start by discussing the new project architecture.

Speaker 1: Thanks Alex. I've been working on the system design. We need to implement three main components: the API gateway, the microservices layer, and the database cluster.

Speaker 0: That sounds good, Sarah. How do you propose we handle the data flow between these components?

Speaker 1: I suggest we use message queues for asynchronous communication and REST APIs for synchronous calls. The API gateway will route requests to appropriate microservices.

Speaker 0: Perfect. What about the database design?

Speaker 1: We'll use a distributed database with read replicas for better performance. Each microservice will have its own database to maintain independence.

Speaker 0: Excellent. Let's also discuss the deployment strategy. We should use containers and orchestration.

Speaker 1: Agreed. I recommend using Docker containers with Kubernetes for orchestration. We can set up CI/CD pipelines for automated deployments.

Speaker 0: Great plan. Let's move forward with this architecture. Any questions from the team?
"""
    
    try:
        # Initialize the diagram service
        print("🔧 Initializing DiagramService...")
        diagram_service = DiagramService()
        print("✅ DiagramService initialized successfully")
        
        # Test generic diagram generation
        print("🎨 Testing generic diagram generation...")
        diagram_path = await diagram_service.create_diagram_from_transcript(sample_transcript)
        
        if diagram_path and os.path.exists(diagram_path):
            file_size = os.path.getsize(diagram_path)
            print(f"✅ Generic diagram generated successfully: {diagram_path} ({file_size} bytes)")
            
            # Clean up
            os.unlink(diagram_path)
        else:
            print("❌ Failed to generate generic diagram")
            return False
        
        # Test custom prompt diagram generation
        print("🎨 Testing custom prompt diagram generation...")
        custom_prompt = "create a system architecture diagram showing the components and their connections"
        custom_diagram_path = await diagram_service.create_diagram_from_transcript(
            sample_transcript, custom_prompt
        )
        
        if custom_diagram_path and os.path.exists(custom_diagram_path):
            file_size = os.path.getsize(custom_diagram_path)
            print(f"✅ Custom diagram generated successfully: {custom_diagram_path} ({file_size} bytes)")
            
            # Clean up
            os.unlink(custom_diagram_path)
        else:
            print("❌ Failed to generate custom diagram")
            return False
        
        print("✅ All tests passed! Diagram generation is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run the integration test."""
    print("🚀 Starting diagram generation integration test...")
    
    success = await test_complete_diagram_pipeline()
    
    if success:
        print("\n🎉 Integration test completed successfully!")
        print("✅ The diagram generation feature is ready to use!")
    else:
        print("\n❌ Integration test failed.")
        print("Please check the logs above for details.")
        
    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
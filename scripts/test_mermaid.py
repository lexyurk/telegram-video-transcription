#!/usr/bin/env python3
"""Test script to verify mermaid-cli installation and functionality."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path


async def test_mermaid_cli():
    """Test if mermaid-cli is properly installed and working."""
    print("🔍 Testing mermaid-cli installation...")
    
    # Test 1: Check if mmdc command exists
    try:
        result = subprocess.run(
            ["mmdc", "--version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ mermaid-cli version: {result.stdout.strip()}")
        else:
            print(f"❌ mermaid-cli not found or not working: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ mmdc command not found. Make sure @mermaid-js/mermaid-cli is installed.")
        return False
    
    # Test 2: Generate a simple diagram
    print("\n🎨 Testing diagram generation...")
    
    simple_diagram = """flowchart TD
    A[Start] --> B{Is it working?}
    B -->|Yes| C[Great!]
    B -->|No| D[Debug]
    C --> E[End]
    D --> E
"""
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as mmd_file:
            mmd_file.write(simple_diagram)
            mmd_file_path = mmd_file.name
        
        output_path = "/tmp/test_diagram.png"
        
        try:
            process = await asyncio.create_subprocess_exec(
                "mmdc",
                "-i", mmd_file_path,
                "-o", output_path,
                "-t", "dark",
                "-b", "transparent",
                "--width", "800",
                "--height", "600",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"✅ Test diagram generated successfully: {output_path} ({file_size} bytes)")
                
                # Clean up
                os.unlink(output_path)
                os.unlink(mmd_file_path)
                
                return True
            else:
                print(f"❌ Failed to generate diagram. Return code: {process.returncode}")
                print(f"stdout: {stdout.decode()}")
                print(f"stderr: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ Error during diagram generation: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up test: {e}")
        return False


async def main():
    """Run the mermaid-cli test."""
    print("🚀 Testing mermaid-cli setup for diagram generation...")
    
    success = await test_mermaid_cli()
    
    if success:
        print("\n✅ All tests passed! mermaid-cli is ready for use.")
    else:
        print("\n❌ Tests failed. Please check the installation.")
        
    return success


if __name__ == "__main__":
    asyncio.run(main())
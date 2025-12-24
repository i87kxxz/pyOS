from setuptools import setup, find_packages

setup(
    name="pyOS",
    version="0.1.0",
    description="Build complete operating systems using Python - compiles to Assembly and Machine Code",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="pyOS Team",
    author_email="contact@pyos.dev",
    url="https://github.com/pyos/pyos",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "pyos": ["boot/*.asm", "boot/*.bin"],
    },
    install_requires=[
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pyos=pyos.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Operating System Kernels",
    ],
    python_requires=">=3.8",
)

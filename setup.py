from setuptools import setup, find_packages

setup(
    name="ttslab",
    description="Run TTS models.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    version="0.1.0",
    packages=find_packages(),
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points={
        "console_scripts": [
            "ttslab=ttslab.cli:app",
        ],
    },
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
    ],
)

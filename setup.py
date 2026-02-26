from setuptools import setup, find_packages

setup(
    name="igo-splunk-logging",
    version="1.0.0",
    description="Shared Splunk HEC logging utility for IGO Python scripts",
    author="IGO",
    author_email="igo@mskcc.org",
    py_modules=["splunk_logging"],
    python_requires=">=3.7",
    install_requires=[
        "splunk_handler>=3.0.0",
        "python-dotenv>=1.0.0",
        "requests",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)

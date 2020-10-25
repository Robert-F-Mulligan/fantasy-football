import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="fantasyfootball",
    version="0.0.1",
    author="Robert F. Mulligan",
    author_email="robert.f.mulligan@gmail.com",
    description="Analysis and data scraping for Fantasy Football",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Robert-F-Mulligan/fantasy-football",
    packages=setuptools.find_packages(include=['fantasyfootball']),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
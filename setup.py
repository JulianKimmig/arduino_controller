import setuptools

with open("requirements.txt") as f:
    required = f.read().splitlines()


setup = dict(
    name="ArduinoController",
    version="0.1",
    author="Julian Kimmig",
    author_email="julian-kimmig@gmx.net",
    description="A highly versatile arduino controller",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/JulianKimmig/arduino_controller",
    packages=setuptools.find_packages(),
    install_requires=required,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
if __name__ == "__main__":
    setuptools.setup(**setup)

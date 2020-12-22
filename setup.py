import setuptools

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name='simantha',
    version='0.0.1',
    author='Michael Hoffman',
    author_email='hoffman@psu.edu',
    description='Simulation of Manufacturing Systems',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/m-hoff/maintsim',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Intended Audience :: Manufacturing',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ]
)

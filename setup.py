import setuptools

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name='maintsim',
    version='0.1.1',
    author='Michael Hoffman',
    author_email='MichaelHoffman@psu.edu',
    description='Simulation of maintenance in manufacturing systems',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/m-hoff/maintsim',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ]
)
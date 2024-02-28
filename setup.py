from setuptools import setup, find_packages

setup(
    name='sbsv',
    version='0.0.1',
    description='SBSV: Square Brackets Separated Values',
    author='shhan',
    author_email='shhan814@gmail.com',
    url='https://github.com/hsh814/sbsv',
    install_requires=[],
    packages=find_packages(exclude=[]),
    keywords=['csv', 'log', 'analysis', 'data'],
    python_requires='>=3.6',
    package_data={},
    zip_safe=False,
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)


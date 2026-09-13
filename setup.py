from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "sbsv._native",
            sources=[
                "sbsv/_native.c",
                "libsbsv/src/sbsv.c",
                "libsbsv/src/sbsv_parser.c",
            ],
            include_dirs=["libsbsv/include"],
            optional=True,
        )
    ]
)

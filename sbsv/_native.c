#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "sbsv.h"

#include <string.h>

#define NATIVE_PARSER_CAPSULE "sbsv._native.Parser"

typedef struct {
    sbsv_parser* parser;
    PyObject* custom_types;
} native_parser;
typedef struct {
    PyObject* converter;
    char* input;
} native_custom_value;


static PyObject* NativeParseError = NULL;

static int unicode_as_c_string(
    PyObject* value,
    const char** output,
    Py_ssize_t* length,
    const char* context
) {
    const char* encoded;
    Py_ssize_t encoded_length;

    if (!PyUnicode_Check(value)) {
        PyErr_Format(PyExc_TypeError, "%s must be str", context);
        return 0;
    }
    encoded = PyUnicode_AsUTF8AndSize(value, &encoded_length);
    if (encoded == NULL) {
        return 0;
    }
    if (memchr(encoded, '\0', (size_t)encoded_length) != NULL) {
        PyErr_Format(PyExc_ValueError, "%s contains an embedded NUL character", context);
        return 0;
    }
    *output = encoded;
    *length = encoded_length;
    return 1;
}

static void set_status_error(sbsv_status status, const sbsv_parser* parser) {
    const char* detail;

    if (status == SBSV_ERR_ALLOC) {
        PyErr_NoMemory();
        return;
    }
    detail = parser == NULL ? NULL : sbsv_parser_last_error(parser);
    if (detail == NULL) {
        detail = sbsv_status_str(status);
    }
    PyErr_SetString(PyExc_ValueError, detail);
}

static void set_native_parse_error(sbsv_status status, const sbsv_parser* parser) {
    const char* detail;

    if (status == SBSV_ERR_ALLOC) {
        PyErr_NoMemory();
        return;
    }
    detail = sbsv_parser_last_error(parser);
    if (detail == NULL) {
        detail = sbsv_status_str(status);
    }
    PyErr_SetString(NativeParseError, detail);
}

static PyObject* value_to_python(const sbsv_value* value) {
    PyObject* result;
    size_t i;

    switch (value->type) {
        case SBSV_VALUE_NULL:
            Py_RETURN_NONE;
        case SBSV_VALUE_INT:
            return PyLong_FromLongLong(value->data.int_value);
        case SBSV_VALUE_UINT:
            return PyLong_FromUnsignedLongLong(value->data.uint_value);
        case SBSV_VALUE_BIG_INT:
            return PyLong_FromString(value->data.string_value, NULL, 10);
        case SBSV_VALUE_BIG_HEX:
            return PyLong_FromString(value->data.string_value, NULL, 16);
        case SBSV_VALUE_FLOAT:
            return PyFloat_FromDouble(value->data.float_value);
        case SBSV_VALUE_BOOL:
            return PyBool_FromLong(value->data.bool_value);
        case SBSV_VALUE_STRING:
            return PyUnicode_DecodeUTF8(
                value->data.string_value,
                (Py_ssize_t)strlen(value->data.string_value),
                "strict"
            );
        case SBSV_VALUE_LIST:
            result = PyList_New((Py_ssize_t)value->data.list.count);
            if (result == NULL) {
                return NULL;
            }
            for (i = 0; i < value->data.list.count; ++i) {
                PyObject* item = value_to_python(&value->data.list.items[i]);
                if (item == NULL) {
                    Py_DECREF(result);
                    return NULL;
                }
                PyList_SET_ITEM(result, (Py_ssize_t)i, item);
            }
            return result;
        case SBSV_VALUE_CUSTOM: {
            native_custom_value* custom = (native_custom_value*)value->data.custom_ptr;
            PyObject* input_object;
            if (custom == NULL) {
                Py_RETURN_NONE;
            }
            input_object = PyUnicode_DecodeUTF8(
                custom->input,
                (Py_ssize_t)strlen(custom->input),
                "strict"
            );
            if (input_object == NULL) {
                return NULL;
            }
            result = PyObject_CallFunctionObjArgs(
                custom->converter,
                input_object,
                NULL
            );
            Py_DECREF(input_object);
            return result;
        }
    }

    PyErr_SetString(PyExc_RuntimeError, "native parser returned an unknown value type");
    return NULL;
}

static PyObject* row_to_python(const sbsv_row* row) {
    PyObject* schema_name;
    PyObject* fields;
    PyObject* result;
    size_t i;

    schema_name = PyUnicode_InternFromString(row->schema_name);
    if (schema_name == NULL) {
        return NULL;
    }

    fields = PyDict_New();
    if (fields == NULL) {
        Py_DECREF(schema_name);
        return NULL;
    }
    for (i = 0; i < row->field_count; ++i) {
        PyObject* field_name = PyUnicode_InternFromString(row->fields[i].name_with_tag);
        PyObject* field_value;
        int status;

        if (field_name == NULL) {
            Py_DECREF(schema_name);
            Py_DECREF(fields);
            return NULL;
        }
        field_value = value_to_python(&row->fields[i].value);
        if (field_value == NULL) {
            Py_DECREF(field_name);
            Py_DECREF(schema_name);
            Py_DECREF(fields);
            return NULL;
        }
        status = PyDict_SetItem(fields, field_name, field_value);
        Py_DECREF(field_name);
        Py_DECREF(field_value);
        if (status < 0) {
            Py_DECREF(schema_name);
            Py_DECREF(fields);
            return NULL;
        }
    }

    result = PyTuple_New(2);
    if (result == NULL) {
        Py_DECREF(schema_name);
        Py_DECREF(fields);
        return NULL;
    }
    PyTuple_SET_ITEM(result, 0, schema_name);
    PyTuple_SET_ITEM(result, 1, fields);
    return result;
}

static void native_custom_value_free(void* ptr) {
    native_custom_value* custom = (native_custom_value*)ptr;
    if (custom == NULL) {
        return;
    }
    PyMem_RawFree(custom->input);
    PyMem_RawFree(custom);
}

static sbsv_status python_custom_type(
    const char* input,
    sbsv_value* out_value,
    void* user_data
) {
    native_custom_value* custom;
    size_t input_length = strlen(input);

    custom = (native_custom_value*)PyMem_RawMalloc(sizeof(native_custom_value));
    if (custom == NULL) {
        return SBSV_ERR_ALLOC;
    }
    custom->input = (char*)PyMem_RawMalloc(input_length + 1);
    if (custom->input == NULL) {
        PyMem_RawFree(custom);
        return SBSV_ERR_ALLOC;
    }
    memcpy(custom->input, input, input_length + 1);
    custom->converter = (PyObject*)user_data;
    return sbsv_value_set_custom_ptr(
        out_value,
        custom,
        native_custom_value_free
    );
}

static native_parser* native_parser_from_capsule(PyObject* capsule) {
    return (native_parser*)PyCapsule_GetPointer(capsule, NATIVE_PARSER_CAPSULE);
}

static void native_parser_capsule_free(PyObject* capsule) {
    native_parser* state = native_parser_from_capsule(capsule);
    if (state == NULL) {
        PyErr_Clear();
        return;
    }
    sbsv_parser_free(state->parser);
    Py_XDECREF(state->custom_types);
    PyMem_Free(state);
}

static PyObject* native_compile_parser(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char* keywords[] = {
        "schemas",
        "custom_types",
        "ignore_unknown",
        "ignored_prefix",
        "save_ignored",
        NULL
    };
    PyObject* schemas_object;
    PyObject* custom_types_object;
    PyObject* ignored_prefix_object = Py_None;
    PyObject* schemas = NULL;
    native_parser* state = NULL;
    int ignore_unknown = 1;
    int save_ignored = 0;
    Py_ssize_t i;
    sbsv_status status;

    (void)self;
    if (!PyArg_ParseTupleAndKeywords(
            args,
            kwargs,
            "OO|pOp:compile_parser",
            keywords,
            &schemas_object,
            &custom_types_object,
            &ignore_unknown,
            &ignored_prefix_object,
            &save_ignored)) {
        return NULL;
    }
    if (!PyDict_Check(custom_types_object)) {
        PyErr_SetString(PyExc_TypeError, "custom_types must be a dict");
        return NULL;
    }

    schemas = PySequence_Fast(schemas_object, "schemas must be a sequence of str");
    if (schemas == NULL) {
        return NULL;
    }
    state = (native_parser*)PyMem_Calloc(1, sizeof(native_parser));
    if (state == NULL) {
        Py_DECREF(schemas);
        return PyErr_NoMemory();
    }
    state->custom_types = PyDict_Copy(custom_types_object);
    if (state->custom_types == NULL) {
        Py_DECREF(schemas);
        PyMem_Free(state);
        return NULL;
    }
    state->parser = sbsv_parser_new(
        ignore_unknown ? SBSV_PARSER_DEFAULT : SBSV_PARSER_NO_IGNORE_UNKNOWN
    );
    if (state->parser == NULL) {
        Py_DECREF(schemas);
        Py_DECREF(state->custom_types);
        PyMem_Free(state);
        return PyErr_NoMemory();
    }

    {
        PyObject* key;
        PyObject* converter;
        Py_ssize_t position = 0;
        while (PyDict_Next(state->custom_types, &position, &key, &converter)) {
            const char* type_name;
            Py_ssize_t type_name_length;
            if (!PyCallable_Check(converter)) {
                PyErr_SetString(PyExc_TypeError, "custom type converter must be callable");
                goto fail;
            }
            if (!unicode_as_c_string(key, &type_name, &type_name_length, "custom type name")) {
                goto fail;
            }
            (void)type_name_length;
            status = sbsv_parser_add_custom_type(
                state->parser,
                type_name,
                python_custom_type,
                converter
            );
            if (status != SBSV_OK) {
                set_status_error(status, state->parser);
                goto fail;
            }
        }
    }

    if (ignored_prefix_object != Py_None) {
        const char* prefix;
        Py_ssize_t prefix_length;
        if (!unicode_as_c_string(
                ignored_prefix_object,
                &prefix,
                &prefix_length,
                "ignored_prefix")) {
            goto fail;
        }
        (void)prefix_length;
        status = sbsv_parser_ignore_prefix(state->parser, prefix, save_ignored);
        if (status != SBSV_OK) {
            set_status_error(status, state->parser);
            goto fail;
        }
    }

    for (i = 0; i < PySequence_Fast_GET_SIZE(schemas); ++i) {
        PyObject* schema_object = PySequence_Fast_GET_ITEM(schemas, i);
        const char* schema;
        Py_ssize_t schema_length;
        if (!unicode_as_c_string(schema_object, &schema, &schema_length, "schema")) {
            goto fail;
        }
        (void)schema_length;
        status = sbsv_parser_add_schema(state->parser, schema);
        if (status != SBSV_OK) {
            set_status_error(status, state->parser);
            goto fail;
        }
    }
    Py_DECREF(schemas);

    {
        PyObject* capsule = PyCapsule_New(
            state,
            NATIVE_PARSER_CAPSULE,
            native_parser_capsule_free
        );
        if (capsule == NULL) {
            sbsv_parser_free(state->parser);
            Py_DECREF(state->custom_types);
            PyMem_Free(state);
        }
        return capsule;
    }

fail:
    Py_DECREF(schemas);
    sbsv_parser_free(state->parser);
    Py_DECREF(state->custom_types);
    PyMem_Free(state);
    return NULL;
}

static PyObject* native_parse_rows(PyObject* self, PyObject* args) {
    PyObject* capsule;
    PyObject* content_object;
    native_parser* state;
    const char* content;
    Py_ssize_t content_length;
    sbsv_status status;
    PyObject* rows;
    Py_ssize_t i;

    (void)self;
    if (!PyArg_ParseTuple(args, "OU:parse_rows", &capsule, &content_object)) {
        return NULL;
    }
    state = native_parser_from_capsule(capsule);
    if (state == NULL) {
        return NULL;
    }
    if (!unicode_as_c_string(content_object, &content, &content_length, "content")) {
        return NULL;
    }
    (void)content_length;

    Py_BEGIN_ALLOW_THREADS
    status = sbsv_parser_loads(state->parser, content);
    Py_END_ALLOW_THREADS
    if (status != SBSV_OK) {
        if (!PyErr_Occurred()) {
            set_native_parse_error(status, state->parser);
        }
        sbsv_parser_clear_rows(state->parser);
        return NULL;
    }

    rows = PyList_New((Py_ssize_t)sbsv_parser_row_count(state->parser));
    if (rows == NULL) {
        sbsv_parser_clear_rows(state->parser);
        return NULL;
    }
    for (i = 0; i < (Py_ssize_t)sbsv_parser_row_count(state->parser); ++i) {
        PyObject* row = row_to_python(sbsv_parser_row_at(state->parser, (size_t)i));
        if (row == NULL) {
            Py_DECREF(rows);
            sbsv_parser_clear_rows(state->parser);
            return NULL;
        }
        PyList_SET_ITEM(rows, i, row);
    }
    sbsv_parser_clear_rows(state->parser);
    return rows;
}

static PyObject* native_parse_line(PyObject* self, PyObject* args) {
    PyObject* capsule;
    PyObject* line_object;
    native_parser* state;
    const char* line;
    Py_ssize_t line_length;
    Py_ssize_t line_number = 0;
    sbsv_row* row = NULL;
    sbsv_status status;
    PyObject* result;

    (void)self;
    if (!PyArg_ParseTuple(args, "OU|n:parse_line", &capsule, &line_object, &line_number)) {
        return NULL;
    }
    state = native_parser_from_capsule(capsule);
    if (state == NULL) {
        return NULL;
    }
    if (!unicode_as_c_string(line_object, &line, &line_length, "line")) {
        return NULL;
    }
    (void)line_length;

    Py_BEGIN_ALLOW_THREADS
    status = sbsv_parser_parse_line_detached(
        state->parser,
        line,
        (size_t)line_number,
        &row
    );
    Py_END_ALLOW_THREADS
    if (status != SBSV_OK) {
        if (!PyErr_Occurred()) {
            set_native_parse_error(status, state->parser);
        }
        return NULL;
    }
    if (row == NULL) {
        Py_RETURN_NONE;
    }
    result = row_to_python(row);
    sbsv_row_free(row);
    return result;
}

static PyObject* native_version(PyObject* self, PyObject* ignored) {
    (void)self;
    (void)ignored;
    return Py_BuildValue(
        "(iii)",
        SBSV_VERSION_MAJOR,
        SBSV_VERSION_MINOR,
        SBSV_VERSION_PATCH
    );
}

static PyMethodDef native_methods[] = {
    {
        "compile_parser",
        (PyCFunction)(void (*)(void))native_compile_parser,
        METH_VARARGS | METH_KEYWORDS,
        PyDoc_STR("Compile schemas and custom converters into a reusable parser.")
    },
    {
        "parse_rows",
        native_parse_rows,
        METH_VARARGS,
        PyDoc_STR("Parse SBSV content with a compiled parser.")
    },
    {
        "parse_line",
        native_parse_line,
        METH_VARARGS,
        PyDoc_STR("Parse one SBSV line with a compiled parser.")
    },
    {
        "version",
        native_version,
        METH_NOARGS,
        PyDoc_STR("Return the linked libsbsv version.")
    },
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef native_module = {
    PyModuleDef_HEAD_INIT,
    "_native",
    "Native libsbsv bridge.",
    -1,
    native_methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC PyInit__native(void) {
    PyObject* module = PyModule_Create(&native_module);
    if (module == NULL) {
        return NULL;
    }
    NativeParseError = PyErr_NewException(
        "sbsv._native.NativeParseError",
        PyExc_ValueError,
        NULL
    );
    if (NativeParseError == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    if (PyModule_AddObject(module, "NativeParseError", NativeParseError) < 0) {
        Py_DECREF(NativeParseError);
        NativeParseError = NULL;
        Py_DECREF(module);
        return NULL;
    }
    return module;
}

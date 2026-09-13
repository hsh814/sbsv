#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "sbsv.h"

#include <string.h>

static int unicode_as_c_string(PyObject* value, const char** output, Py_ssize_t* length, const char* context) {
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

static PyObject* value_to_python(const sbsv_value* value) {
    PyObject* result;
    size_t i;

    switch (value->type) {
        case SBSV_VALUE_NULL:
            Py_RETURN_NONE;
        case SBSV_VALUE_INT:
            return PyLong_FromLongLong(value->data.int_value);
        case SBSV_VALUE_BIG_INT:
            return PyLong_FromString(value->data.string_value, NULL, 10);
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
        case SBSV_VALUE_CUSTOM:
            PyErr_SetString(PyExc_RuntimeError, "native parser received an unsupported custom value");
            return NULL;
    }

    PyErr_SetString(PyExc_RuntimeError, "native parser returned an unknown value type");
    return NULL;
}

static PyObject* row_to_python(const sbsv_row* row) {
    PyObject* schema_name;
    PyObject* fields;
    PyObject* result;
    size_t i;

    schema_name = PyUnicode_DecodeUTF8(
        row->schema_name,
        (Py_ssize_t)strlen(row->schema_name),
        "strict"
    );
    if (schema_name == NULL) {
        return NULL;
    }

    fields = PyDict_New();
    if (fields == NULL) {
        Py_DECREF(schema_name);
        return NULL;
    }
    for (i = 0; i < row->field_count; ++i) {
        PyObject* field_name = PyUnicode_DecodeUTF8(
            row->fields[i].name_with_tag,
            (Py_ssize_t)strlen(row->fields[i].name_with_tag),
            "strict"
        );
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

static PyObject* native_parse_rows(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char* keywords[] = {
        "content",
        "schemas",
        "ignore_unknown",
        "ignored_prefix",
        "save_ignored",
        NULL
    };
    PyObject* content_object;
    PyObject* schemas_object;
    PyObject* ignored_prefix_object = Py_None;
    PyObject* schemas;
    const char* content;
    Py_ssize_t content_length;
    int ignore_unknown = 1;
    int save_ignored = 0;
    sbsv_parser* parser;
    sbsv_status status;
    PyObject* rows;
    Py_ssize_t i;

    (void)self;
    if (!PyArg_ParseTupleAndKeywords(
            args,
            kwargs,
            "UO|pOp:parse_rows",
            keywords,
            &content_object,
            &schemas_object,
            &ignore_unknown,
            &ignored_prefix_object,
            &save_ignored)) {
        return NULL;
    }
    if (!unicode_as_c_string(content_object, &content, &content_length, "content")) {
        return NULL;
    }
    (void)content_length;

    schemas = PySequence_Fast(schemas_object, "schemas must be a sequence of str");
    if (schemas == NULL) {
        return NULL;
    }
    parser = sbsv_parser_new(
        ignore_unknown ? SBSV_PARSER_DEFAULT : SBSV_PARSER_NO_IGNORE_UNKNOWN
    );
    if (parser == NULL) {
        Py_DECREF(schemas);
        return PyErr_NoMemory();
    }

    if (ignored_prefix_object != Py_None) {
        const char* prefix;
        Py_ssize_t prefix_length;
        if (!unicode_as_c_string(
                ignored_prefix_object,
                &prefix,
                &prefix_length,
                "ignored_prefix")) {
            sbsv_parser_free(parser);
            Py_DECREF(schemas);
            return NULL;
        }
        (void)prefix_length;
        status = sbsv_parser_ignore_prefix(parser, prefix, save_ignored);
        if (status != SBSV_OK) {
            set_status_error(status, parser);
            sbsv_parser_free(parser);
            Py_DECREF(schemas);
            return NULL;
        }
    }

    for (i = 0; i < PySequence_Fast_GET_SIZE(schemas); ++i) {
        PyObject* schema_object = PySequence_Fast_GET_ITEM(schemas, i);
        const char* schema;
        Py_ssize_t schema_length;
        if (!unicode_as_c_string(schema_object, &schema, &schema_length, "schema")) {
            sbsv_parser_free(parser);
            Py_DECREF(schemas);
            return NULL;
        }
        (void)schema_length;
        status = sbsv_parser_add_schema(parser, schema);
        if (status != SBSV_OK) {
            set_status_error(status, parser);
            sbsv_parser_free(parser);
            Py_DECREF(schemas);
            return NULL;
        }
    }
    Py_DECREF(schemas);

    Py_BEGIN_ALLOW_THREADS
    status = sbsv_parser_loads(parser, content);
    Py_END_ALLOW_THREADS
    if (status != SBSV_OK) {
        set_status_error(status, parser);
        sbsv_parser_free(parser);
        return NULL;
    }

    rows = PyList_New((Py_ssize_t)sbsv_parser_row_count(parser));
    if (rows == NULL) {
        sbsv_parser_free(parser);
        return NULL;
    }
    for (i = 0; i < (Py_ssize_t)sbsv_parser_row_count(parser); ++i) {
        PyObject* row = row_to_python(sbsv_parser_row_at(parser, (size_t)i));
        if (row == NULL) {
            Py_DECREF(rows);
            sbsv_parser_free(parser);
            return NULL;
        }
        PyList_SET_ITEM(rows, i, row);
    }

    sbsv_parser_free(parser);
    return rows;
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
        "parse_rows",
        (PyCFunction)native_parse_rows,
        METH_VARARGS | METH_KEYWORDS,
        PyDoc_STR("Parse SBSV content and return (schema_name, fields) rows.")
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
    return PyModule_Create(&native_module);
}

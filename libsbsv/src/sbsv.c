#include "sbsv.h"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char raw;
    const char* escaped;
    size_t escaped_len;
} sbsv_escape_entry;

static const sbsv_escape_entry ESCAPE_TABLE[] = {
    {'\b', "\\b", 2},
    {'\t', "\\t", 2},
    {'\n', "\\n", 2},
    {'\f', "\\f", 2},
    {'\r', "\\r", 2},
    {'\"', "\\\"", 2},
    {'/', "\\/", 2},
    {'\\', "\\\\", 2},
    {'[', "\\[", 2},
    {']', "\\]", 2},
    {',', "\\,", 2},
    {':', "\\:", 2},
};

static const size_t ESCAPE_TABLE_SIZE = sizeof(ESCAPE_TABLE) / sizeof(ESCAPE_TABLE[0]);

const char* sbsv_status_str(sbsv_status status) {
    switch (status) {
        case SBSV_OK:
            return "ok";
        case SBSV_ERR_INVALID_ARG:
            return "invalid argument";
        case SBSV_ERR_ALLOC:
            return "allocation failed";
        default:
            return "unknown status";
    }
}

static sbsv_status sbsv_copy_to_heap(const char* src, size_t len, char** output) {
    char* result;

    if (output == NULL) {
        return SBSV_ERR_INVALID_ARG;
    }

    result = (char*)malloc(len + 1);
    if (result == NULL) {
        return SBSV_ERR_ALLOC;
    }

    if (len > 0) {
        memcpy(result, src, len);
    }
    result[len] = '\0';

    *output = result;
    return SBSV_OK;
}

static bool sbsv_is_space(char ch) {
    return ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r' || ch == '\f' || ch == '\v';
}

static void sbsv_trim_view(const char** start, const char** end) {
    while (*start < *end && sbsv_is_space(**start)) {
        *start += 1;
    }

    while (*end > *start && sbsv_is_space(*(*end - 1))) {
        *end -= 1;
    }
}

static sbsv_status sbsv_append_char(char** buffer, size_t* len, size_t* cap, char ch) {
    char* new_buffer;

    if (*len + 1 >= *cap) {
        size_t new_cap = (*cap == 0) ? 16 : (*cap * 2);
        while (*len + 1 >= new_cap) {
            new_cap *= 2;
        }
        new_buffer = (char*)realloc(*buffer, new_cap);
        if (new_buffer == NULL) {
            return SBSV_ERR_ALLOC;
        }
        *buffer = new_buffer;
        *cap = new_cap;
    }

    (*buffer)[*len] = ch;
    *len += 1;
    (*buffer)[*len] = '\0';
    return SBSV_OK;
}

static sbsv_status sbsv_append_token(sbsv_token_list* tokens, char* token) {
    char** new_items;

    new_items = (char**)realloc(tokens->items, sizeof(char*) * (tokens->count + 1));
    if (new_items == NULL) {
        return SBSV_ERR_ALLOC;
    }

    tokens->items = new_items;
    tokens->items[tokens->count] = token;
    tokens->count += 1;
    return SBSV_OK;
}

static sbsv_status sbsv_finalize_token(const char* token_buf, bool should_unescape, sbsv_token_list* out_tokens) {
    const char* start;
    const char* end;
    char* raw_token = NULL;
    char* final_token = NULL;
    sbsv_status status;

    start = token_buf;
    end = token_buf + strlen(token_buf);
    sbsv_trim_view(&start, &end);

    status = sbsv_copy_to_heap(start, (size_t)(end - start), &raw_token);
    if (status != SBSV_OK) {
        return status;
    }

    if (should_unescape) {
        status = sbsv_unescape_str(raw_token, &final_token);
        free(raw_token);
        if (status != SBSV_OK) {
            return status;
        }
    } else {
        final_token = raw_token;
    }

    status = sbsv_append_token(out_tokens, final_token);
    if (status != SBSV_OK) {
        free(final_token);
        return status;
    }

    return SBSV_OK;
}

sbsv_status sbsv_escape_str(const char* input, char** output) {
    size_t index;
    size_t length;
    size_t out_len;
    size_t out_cap;
    char* result;

    if (input == NULL || output == NULL) {
        return SBSV_ERR_INVALID_ARG;
    }

    length = strlen(input);
    out_cap = length * 2 + 1;
    if (out_cap < 16) {
        out_cap = 16;
    }

    result = (char*)malloc(out_cap);
    if (result == NULL) {
        return SBSV_ERR_ALLOC;
    }
    out_len = 0;
    result[0] = '\0';

    for (index = 0; index < length; ++index) {
        bool replaced = false;
        size_t entry_index;
        for (entry_index = 0; entry_index < ESCAPE_TABLE_SIZE; ++entry_index) {
            if (input[index] == ESCAPE_TABLE[entry_index].raw) {
                size_t needed = out_len + ESCAPE_TABLE[entry_index].escaped_len + 1;
                if (needed > out_cap) {
                    size_t new_cap = out_cap * 2;
                    char* new_result;
                    while (needed > new_cap) {
                        new_cap *= 2;
                    }
                    new_result = (char*)realloc(result, new_cap);
                    if (new_result == NULL) {
                        free(result);
                        return SBSV_ERR_ALLOC;
                    }
                    result = new_result;
                    out_cap = new_cap;
                }
                memcpy(result + out_len, ESCAPE_TABLE[entry_index].escaped, ESCAPE_TABLE[entry_index].escaped_len);
                out_len += ESCAPE_TABLE[entry_index].escaped_len;
                result[out_len] = '\0';
                replaced = true;
                break;
            }
        }

        if (!replaced) {
            sbsv_status st = sbsv_append_char(&result, &out_len, &out_cap, input[index]);
            if (st != SBSV_OK) {
                free(result);
                return st;
            }
        }
    }

    *output = result;
    return SBSV_OK;
}

sbsv_status sbsv_unescape_str(const char* input, char** output) {
    size_t length;
    size_t i;
    size_t out_len;
    char* result;

    if (input == NULL || output == NULL) {
        return SBSV_ERR_INVALID_ARG;
    }

    length = strlen(input);
    result = (char*)malloc(length + 1);
    if (result == NULL) {
        return SBSV_ERR_ALLOC;
    }

    out_len = 0;
    i = 0;
    while (i < length) {
        if (input[i] == '\\' && i + 1 < length) {
            bool matched = false;
            size_t entry_index;
            for (entry_index = 0; entry_index < ESCAPE_TABLE_SIZE; ++entry_index) {
                if (input[i + 1] == ESCAPE_TABLE[entry_index].escaped[1]) {
                    result[out_len++] = ESCAPE_TABLE[entry_index].raw;
                    i += 2;
                    matched = true;
                    break;
                }
            }
            if (matched) {
                continue;
            }
        }

        result[out_len++] = input[i];
        i += 1;
    }

    result[out_len] = '\0';
    *output = result;
    return SBSV_OK;
}

sbsv_status sbsv_tokenize_line(const char* line, sbsv_token_list* out_tokens) {
    int level;
    size_t length;
    size_t i;
    bool escape;
    bool should_unescape;
    char* current;
    size_t current_len;
    size_t current_cap;
    sbsv_status status;

    if (line == NULL || out_tokens == NULL) {
        return SBSV_ERR_INVALID_ARG;
    }

    out_tokens->items = NULL;
    out_tokens->count = 0;

    level = 0;
    length = strlen(line);
    escape = false;
    should_unescape = false;
    current = NULL;
    current_len = 0;
    current_cap = 0;

    status = sbsv_append_char(&current, &current_len, &current_cap, '\0');
    if (status != SBSV_OK) {
        return status;
    }
    current_len = 0;

    for (i = 0; i < length; ++i) {
        char ch = line[i];

        if (escape) {
            escape = false;
            status = sbsv_append_char(&current, &current_len, &current_cap, '\\');
            if (status != SBSV_OK) {
                free(current);
                sbsv_free_token_list(out_tokens);
                return status;
            }
            status = sbsv_append_char(&current, &current_len, &current_cap, ch);
            if (status != SBSV_OK) {
                free(current);
                sbsv_free_token_list(out_tokens);
                return status;
            }
            continue;
        }

        if (ch == '\\') {
            escape = true;
            should_unescape = true;
            continue;
        }

        if (ch == '[') {
            level += 1;
            if (level == 1) {
                if (current_len > 0) {
                    status = sbsv_finalize_token(current, should_unescape, out_tokens);
                    if (status != SBSV_OK) {
                        free(current);
                        sbsv_free_token_list(out_tokens);
                        return status;
                    }
                    should_unescape = false;
                }
                current_len = 0;
                current[0] = '\0';
                continue;
            }
        } else if (ch == ']') {
            level -= 1;
            if (level == 0) {
                status = sbsv_finalize_token(current, should_unescape, out_tokens);
                if (status != SBSV_OK) {
                    free(current);
                    sbsv_free_token_list(out_tokens);
                    return status;
                }
                should_unescape = false;
                current_len = 0;
                current[0] = '\0';
                continue;
            }
        }

        if (level > 0) {
            status = sbsv_append_char(&current, &current_len, &current_cap, ch);
            if (status != SBSV_OK) {
                free(current);
                sbsv_free_token_list(out_tokens);
                return status;
            }
        }
    }

    free(current);
    return SBSV_OK;
}

void sbsv_free_token_list(sbsv_token_list* tokens) {
    size_t i;

    if (tokens == NULL || tokens->items == NULL) {
        return;
    }

    for (i = 0; i < tokens->count; ++i) {
        free(tokens->items[i]);
    }

    free(tokens->items);
    tokens->items = NULL;
    tokens->count = 0;
}

void sbsv_free_string(char* value) {
    free(value);
}

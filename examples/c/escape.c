#include <stdlib.h>

char *sbsv_escape_square_brackets(char *original) {
  // Check for NULL input
  if (original == NULL) {
    return NULL;
  }
  
  // Count square brackets and get original length
  int bracket_count = 0;
  int original_length = 0;
  for (int i = 0; original[i] != '\0'; i++) {
    if (original[i] == '[' || original[i] == ']') {
      bracket_count++;
    }
    original_length++;
  }
  
  // Allocate memory for the new string
  // Size: original length + bracket count (for backslashes) + 1 (null terminator)
  char *escaped = (char *) malloc(original_length + bracket_count + 1);
  if (escaped == NULL) {
    return NULL;  // Memory allocation failed
  }
  
  // Copy original to new string, escaping square brackets
  int j = 0;  // Index for the escaped string
  for (int i = 0; original[i] != '\0'; i++) {
    if (original[i] == '[' || original[i] == ']') {
      // Add backslash before bracket
      escaped[j++] = '\\';
    }
    // Add the current character
    escaped[j++] = original[i];
  }
  
  // Null-terminate the escaped string
  escaped[j] = '\0';
  
  return escaped;
}
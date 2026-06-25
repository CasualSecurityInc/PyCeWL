## MUTATIONS HOWTO

Use a short first-pass rule set before trying larger expansions.

### Common suffixes/prefixes

This example uses hashcat in stdout rule mode: `--stdout` prints generated candidates instead of cracking, and `-r <rulefile>` applies a custom rule file to each input word.

```bash
cat > specials.rule <<'EOF'
$!
$@
$#
^!
^@
$2$0$2$4$!
EOF

hashcat --stdout words.txt -r specials.rule | head -10
```

Use this for quick coverage of common symbol suffixes, symbol prefixes, and a simple year+symbol pattern.

Example `words.txt`:

```text
summer
welcome
support
```

Example output:

```text
summer!
summer@
summer#
!summer
@summer
summer2024!
welcome!
welcome@
welcome#
!welcome
```

### Separator variants

For `word-word`, `word_word`, and `word.word`, use a small helper:

```bash
while read -r w; do printf '%s-%s\n%s_%s\n%s.%s\n' "$w" "$w" "$w" "$w" "$w" "$w"; done < words.txt | head -10
```

This is useful because these middle-separator patterns are awkward to express cleanly in a small hashcat rule file.

Example output:

```text
summer-summer
summer_summer
summer.summer
welcome-welcome
welcome_welcome
welcome.welcome
support-support
support_support
support.support
```

Typical candidates: `Summer2024!`, `Welcome!`, `support@`, `Admin2024!`, `winter-winter`.

### Lowercase, `123!`, `2025!`, doubled punctuation

This second rule file is for wordlists that preserve source capitalization. It lowercases first, then emits a few common numeric and punctuation endings.

```bash
cat > extended.rule <<'EOF'
l
$1$2$3$!
$2$0$2$4$!
$2$0$2$5$!
$!
$!
EOF

hashcat --stdout words.txt -r extended.rule | head -10
```

Example `words.txt`:

```text
EIA
ABC
Support
```

Example output:

```text
eia123!
eia2024!
eia2025!
eia!
eia!!
abc123!
abc2024!
abc2025!
abc!
abc!!
```

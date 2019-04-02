#!/usr/bin/env python
"""
Read a dataset in conllu format from stdin,
 * check against some common errors
 * write correct(ed) sentences to stdout
 * write invalid sentences to stderr
"""

import re
import sys

FORMAT_FOR_DEPREL = re.compile('^[a-z]+(:[a-z]+)?$')

# FORMAT_FOR_DEPS = re.compile('^[a-z]+(:[a-z]+)?(:[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(_[\p{Ll}\p{Lm}\p{Lo}\p{M}]+)*)?(:[a-z]+)?$')
# This regexp didnt immediately work, for now, I just forget about unicode chars in DEPS. 
# Does not practically happen in my case.
FORMAT_FOR_DEPS = re.compile('^[a-z]+(:[a-z]+)?(:[a-zA-Z0-9]+(_[a-zA-Z0-9]+)*)?(:[a-z]+)?$')

def patch_token(token):
    """
    Patch mistakes in the token, but dont consider the token itself invalid.

    Remove invalid entries in DEPS, and DEPREL.
    Remove trailing and leading whitespace

    Returns a token (ie. array of fields)
    """
    if not FORMAT_FOR_DEPREL.match(token[7]):
        token[7] = '_'

    if not FORMAT_FOR_DEPS.match(token[8]):
        token[8] = '_'

    return [field.strip() for field in token]

def patch_sentence(sentence):
    """
    Patch mistakes in the sentence

    Fix subindex
    """

    def parse_a_dot_b(index):
        if (index.find('.') > -1):
            s = index.split('.')
            a = int(s[0])
            b = int(s[1])
        else:
            a = int(index[0])
            b = None
        return a, b

    prev_a, prev_b = 0, 1
    for token in sentence:
        a, b = parse_a_dot_b(token[0])
        if b:
            if a == prev_a and b <= prev_b:
                # change "10.1 .. 10.1" in "10.1 .. 10.2"
                b = prev_b + 1

            token[0] = "{}.{}".format(a, b)
            prev_a = a
            prev_b = b
        else:
            # no subtoken, so reset the subtoken counter
            prev_a = a
            prev_b = 0

    return sentence

def check_sentence(sentence):
    """
    Check the sentence for consistency.

    Returns:
       "ok"     if the sentence is ok
       reason   reason why the sentence is incorrect
    """
    found_root = False
    ntokens = len(sentence)
    for token in sentence:
        try:
            # index can be '6', or '6.1'
            a_dot_b = token[0].split('.')
            index = int(a_dot_b[0])

            # sub is not used, and this will raise another exception if it doesnt exist
            # sub = int(a_dot_b[1])
        except:
            return "Index is malformed: {}".format(index)

        if token[6] != '_':
            try:
                head = int(token[6])
            except:
                return "HEAD is malformed: {}".format(token[6])

            # HEAD should point in the sentence
            if (head < 0 or head > ntokens):
                return "DEP points outside sentence for token {}".format(index)

            # Only root can have DEP = 0
            if (head == 0 and token[7] != 'root'):
                return "DEP is 0 but token is no root {}".format(index)

            # DEP cannot point to itself
            if (head == index):
                return "DEP points to itself for token {}".format(index)

        # there can be only one root
        if token[7] == 'root':
            if head != 0:
                return "root should have head = 0, not {}".format(head)
            if not found_root:
                found_root = True
            else:
                return "Second root encountered at token {}".format(index)

    return "ok"

class ParsingError(UserWarning):
    def __init__(self, message):
        self.message = message

correct_counter = 0
issue_counter = 0
line_counter = 0
sentence_counter = 0
sentence = []
comment_sentid = None
comment_text = None

issuelist = []

for line in sys.stdin:
    line = line.rstrip()
    line_counter += 1

    if len(line) == 0:
        # we read the last token
        sentence_counter += 1
        sentence = patch_sentence(sentence)

        # reconstruct the full sentence
        full_sentence = comment_sentid + "\n" + comment_text + "\n"
        for token in sentence:
            full_sentence += '\t'.join(token) + "\n"

        status = check_sentence(sentence)
        if status == "ok":
            print (full_sentence)
            correct_counter += 1
        else:
            issuelist.append("# " + status + "\n" + full_sentence)
            issue_counter += 1
        
        # reset sentence and metadata
        sentence = []
        comment_sentid = None
        comment_text = None
        continue

    if line[0:9] == '# text = ':
        # read the sentence raw text
        comment_text = line
        continue
    if line[0:12] == '# sent_id = ':
        # read the sentence id
        comment_sentid = line
        continue
    elif line[0] == '#':
        # comments are ignored
        continue

    fields = line.split('\t')
    if len(fields) == 10:
        # the line contains a regular token
        sentence.append(patch_token(fields))
        continue

    raise ParsingError('Error parsing line {}: "{}"'.format(line_counter, line))

print ('Parsed {} sentences and {} tokens.'.format(sentence_counter, line_counter), file=sys.stderr)
print ('Correct sentences: {}'.format(correct_counter), file=sys.stderr)
print ('Incorrect sentences: {}'.format(issue_counter), file=sys.stderr)
print ("\n".join(issuelist), file=sys.stderr)

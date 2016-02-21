import os
import io
import re
import sys
import platform
import argparse
import peglet
import shutil
import subprocess

class Parser(object):
    """This is a docstring"""

    Grammar = r"""
    lines       = _ line _ lines
                | _ line
    line        = num _ statement                        hug
                | statement                              hug
    statement        = printState
                | letState
                | inputState
                | ifState
                | gotoState
                | clearState
                | listState
                | runState
                | endState
                | remState

    printState  = (PRINT\b) _ expr_list
    letState    = (LET\b) _ var _ (?:=) _ expr
                | (LET\b) _ var _ (?:=) _ str
    inputState  = (INPUT\b) _ var_list
    ifState     = (IF\b) _ expr _ (THEN\b) _ statement
    gotoState   = (GOTO\b) _ expr
    remState    = (REM\b) _ str
    listState   = (LIST\b)
    clearState  = (CLEAR\b)
    endState    = (END\b)
    runState    = (RUN\b)

    expr_list   = expr _ , _ expr_list
                | expr
                | str _ , _ expr_list
                | str
    expr        = term _ binop _ expr               join
                | term _ relop _ expr               join
                | term
    term        = var
                | num
                | l_paren _ expr _ r_paren          join
    var_list    = var _ , _ var_list
                | var
    var         = ([A-Z])
                | str

    str         = " chars " _                       join quote
                | ' sqchars ' _                     join
                | chars _
    chars       = char chars                        join
                |
    char        = ([^\x00-\x1f"\\])
                | esc_char
    sqchars     = sqchar sqchars
                |
    sqchar      = ([^\x00-\x1f'\\])
                | esc_char
    esc_char    = \\(['"/\\])
                | \\([bfnrt])                       escape
    num         = (\-) num
                | (\d+)
    relop       = (<>|><|<=|<|>=|>|=)               tokeniser
    binop       = (\+|\-|\*|\/)
    l_paren     = (\()
    r_paren     = (\))
    _           = \s*
    """

    def __init__(self):
        keywords = {
        "escape": re.escape, #Return string with all non-alphanumerics backslashed
        "hug": peglet.hug, # "Return a tuple of all the arguments."
        "join": peglet.join,# "Return all the arguments (strings) concatenated into one string."
        "tokeniser": self.tokeniser, # converts tokens
        "quote": self.quote, #return the quoted token (add quotes at the start an end)
        }
        self.parser = peglet.Parser(self.Grammar, **keywords)

    def __call__(self, program):
        return self.parser(program)

    def tokeniser(self, token):
        """
        This function converts tokens
        :param token: The token to be converted
        """
        # if the token is the not-equal token, return "!="
        if token == "<>" or token == "><":
            return "!="
        # else return the token as is
        return token

    def quote(self, token):
        """
        This function return the quoted token (add quotes at the start and end)
        :param token: The token to be quoted
        """
        return '"%s"' % token
class Compiler(object):

    def __init__(self):
        """
        Initializing the class' members
        """
        self.parser = Parser()
        self.parse_tree = None
        self.symbols = {}
        self.malloc_symbols = {} # a dictionary that holds key-value pairs of the

    def __call__(self, program):
        # starting to output the compiled C code
        sys.stdout = open("tempi.c", 'wb')
        self.parse_tree = self.parser(program)
        # starting to output the compiled C code
        print "#include <stdio.h>"
        print "#include <stdlib.h>"
        print "#include <string.h>"
        print "int main (void) {"
        for line in self.parse_tree:
            if "LET" in line:                     # if the line contains the keyword 'LET' (initializing a variable)
                id = line[2]                      # we get the symbol which will be at index 2
                if id not in self.symbols:        # if the symbol is not already in the symbols collection
                    self.compileState(line[1:])   # we compile the line
            elif "INPUT" in line:                 # if the line contains the keyword 'INPUT' (prompting for input)
                id = line[2]                      # we get the symbol which will be at index 2
                if id not in self.symbols:        # if the symbol is not already in the symbols collection
                    self.compile_var((id, '""'))  # we compile the variable
        for line in self.parse_tree:
            self.compileState(line)               # for each line in the lines to be compiled, we compile the line
        print "}"                                 # outputting the closing bracket

        sys.exit()

    def compileState(self, statement):
        """
        This function compiles a TinyBasic statement into C code
        :param statement: the statement to be compiled, as a list
        """
        start, finish = statement[0], statement[1:]
        # if the finish is not empty, meaning the statement has two words or more
        if finish:
            if start == "IF":                   # if the statement starts with 'IF'
                self.compile_if(finish)          # we compile the 'IF' clause (finish)
            elif start == "LET":                # if the statement starts with 'LET
                self.compile_var(finish)         # we initialize the variable after 'LET' (finish)
            elif start == "REM":                # if the statement starts with 'REM'
                self.compile_comment(finish)     # we compile the comment (finish)
            elif start == "GOTO":               # if the statement starts with 'GOTO'
                self.compile_goto(finish)        # we compile the GOTO statment (finish)
            elif start == "PRINT":              # if the statement starts with 'PRINT'
                self.compile_printf(finish)      # we print the content of the statement (finish)
            elif start == "INPUT":              # if the statement starts with 'INPUT'
                self.compile_input(finish)       # we compile the INPUT statement
            else:                              # if not one of the previous cases
                self.compile_label(start)       # we add a new label (start)
                self.compileState(finish)        # we compile the statement (finish)
        # if the finish is empty, meaning the statement has just one word
        else:
            if start == "END":                  # if the start of the statement is equal to 'END'
                self.compile_return()

    def compile_input(self, tuple):
        """
        This function compiles an input statement (starts with 'INPUT')
        :param tuple: the finish of the input statement (the statement without the 'INPUT' keyword)
        """

        id, buffer = tuple[0], 50# setting the name of the variable in 'id', setting the allocated buffer to 50 bytes (by default)
        self.malloc_symbols[id] = buffer# adding the variable to the dictionary of allocated variables

        # outputting the code needed for initializing the variable
        # first we allocated the needed space (in this case 50 bytes, dafault)
        # second we get the input from the standard input using the 'fgets()' method
        # third, we append the null-terminating character to the inputted string, if the user taps ENTER
        print "{0} = malloc(sizeof(char) * {1}); \n\
fgets({0}, {1}, stdin); \n\
if ({0}[strlen({0}) - 1] == '\\n') {{ \n\
{0}[strlen({0}) - 1] = '\\0'; \n\
}}".format(id, buffer)

    def compile_if(self, tuple):
        """
        This function compiles an IF statement (starts with 'IF')
        :param tuple: the finish of the IF statement (the statement without the 'IF' keyword)
        """

        condition, statement = tuple[0], tuple[2:]# setting the condition to be the part at index 0, and the IF statement to be the rest starting from index 2
        print "if (%s) {" % (condition)# outputting the compiled IF statement (if, condition, opening bracket, statement, closing bracket)
        self.compileState(statement)
        print "}"

    def compile_goto(self, tuple):
        """
        This function compiles a GOTO statement (starts with 'GOTO')
        :param tuple: the finish of the GOTO statement (the statement without the 'GOTO' keyword)
        """

        print "goto label_%s;" % tuple[0]# outputting the compiled GOTO statement, the label is 'label_XX' where XX is the label (found at index 0)

    def compile_var(self, tuple):
        """
        This function compiles a variable declaration and initialization (starts with 'LET')
        :param tuple: the finish of the LET statement (the statement without the 'LET' keyword)
        """

        id = tuple[0]# setting 'id' to variable name (the element at index 0)
        if id in self.symbols: # if the variable is already in the dictionary of symbols
            self.compile_var_set(tuple)# we call the initialization method
        else:# if the variable is NOT already in the dictionary of symbols
            self.compile_var_dec(tuple)# we call the declaration method

    def compile_var_dec(self, tuple):
        """
        This method outputs the necessary code to declare a variable in C (type and name of the variable)
        :param tuple: the finish of the LET statement (the statement without the 'LET' keyword)
        """

        t, id, v = None, tuple[0], tuple[1]# setting the type to None, name to the element at index 0, and value to the element at index 1

        if self.is_quoted(v):# if the value of the variable is quoted (contains quotes), then set the type to 'char'
            t = "char"
        else:# if the value of the variable is NOT quoted, then set the type to 'int'
            t = "int"
        self.symbols[id] = (t, v)# adding the variable name and value as a tuple to the symbols dictionary

        # print the corresponding declaration statements in C
        if t == "char":
            print "%s* %s;" % (t, id)
        elif t == "int":
            print "%s %s;" % (t, id)

    def compile_var_set(self, tuple):
        """
        This method outputs the necessary code to set the value of a variable in C
        :param tuple: the finish of the LET statement (the statement without the 'LET' keyword)
        """

        id, nv = tuple[0], tuple[1]    # getting the variable name, and the new value
        t, ov = self.symbols[id] # getting the type of the variable and its old value
        self.symbols[id] = (t, nv)# setting the variable in the dictionary, with its type and new value
        print "%s = %s;" % (id, nv)# print the corresponding setting statements in C code

    def compile_comment(self, tuple):
        """
        This method outputs the comments in C style
        :param tuple: the finish of the REM statement (the statement without the 'REM' keyword)
        """
        print "// %s" % tuple[0].replace('"', "")

    def compile_label(self, n):
        """
        This method outputs the lable statement
        :param n: the number of the label
        """
        print "label_%s:" % n

    def compile_printf(self, tuple):
        """
        This function compiles a PRINT statement (starts with 'PRINT')
        :param tuple: the finish of the PRINT statement (the statement without the 'PRINT' keyword)
        """

        fmt, args = [], []# fmt will be the placeholders, args will be the actual arguments

        for x in tuple:# for each word in the finish part of the PRINT statement
            if x in self.symbols:          # if the word is already in the dictionary of symbols (variables)
                t, v = self.symbols[x]     # getting the variable's name and type
                if t == "char":            # if the type is char, we add a '%s' to the placeholders list
                    fmt.append("%s")
                elif t == "int":           # if the type is int, we add a '%d' to the placeholders list
                    fmt.append("%d")
                args.append(x)             # we add the variable to the arguments list

            else:                          # if the word is NOT already in the dictionary of symbols (variables)
                try:
                    x = int(eval(x))       # we try to evaluate it as an integer
                    fmt.append("%d")       # if no exception raises, we add a '%d' to the placeholders list
                    args.append(str(x))    # we add the variable to the arguments list (as a string)
                except:                    # if a exception raises while trying to evaluate as an integer
                    fmt.append("%s")       # if an exception raises, we add a '%s' to the placeholders list
                    args.append(x)         # we add the variable to the arguments list
        # if both fmt and args are not empty
        if fmt and args:
            fmt = " ".join(fmt)      # we join the placeholders with whitespaces (as a string)
            args = ", ".join(args)   # we join the argument with commas (as a string)
            # outputting the corresponding printf() statement
            print 'printf("{0}\\n", {1});'.format(fmt, args)

    def compile_return(self):
        """
        This function outputs the necessary code before the end of the program (freeing allocated ressources)
        """
        for id in self.malloc_symbols:# for each variable in the dictionnary of variables allocated in memory
            print "free(%s);" % id# we free the memory allocated for that variable
        print "return 0;" # we add the necessary return statement for the main() method

    def is_quoted(self, s):
        """
        This function verifies if a string is quoted
        :param s: The string to be verified if quoted
        :return: Ture if the string s is quoted, False otherwise
        """
        return re.match('^".*"$', s)
class TinyBasic(object):

    def __init__(self):
        """
        Initializing the class' members
        """
        self.parser = Parser()
        self.compiler = Compiler()

    def parse(self, program):
        return self.parser(program)

    def compile(self, program):
        self.compiler(program)

if __name__ == "__main__":

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("path", nargs='?')
    arg_parser.add_argument("-p", "--parse", action="store_true")
    arg_parser.add_argument("-o", "--output", help="Output file")
    #arg_parser.add_argument("-c", "--compile", action="store_true")
    args = arg_parser.parse_args()

    #FakeInterpreter() #call our fake interpreter
    tiny_basic = TinyBasic()# instantiate a new TinyBasic() instance

    if args.output:
        with io.open(args.output, 'w') as output_file:

            #output_file.write(copyfile_read.decode('utf8'))
            #output_file.close()
            #os.rename(temp, args.output)
            os.rename("tempi.c", args.output)

    if args.path:# if the path argument exists
        if os.path.isfile(args.path):# if the path points to a file
            with io.open(args.path, "r") as f:# we open the file in read mode
                program = "".join(f.readlines())# we read all the lines from the file
                program = program.encode("ascii", "ignore")# we apply the proper encoding
                if args.parse:# if the user chooses to parse
                    for line in tiny_basic.parse(program):
                        print line
                else: #else compile
                    tiny_basic.compile(program)
        else:
            print "[!] Error: File doesn't exist"

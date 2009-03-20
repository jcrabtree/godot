#------------------------------------------------------------------------------
#  Copyright (c) 2008 Richard W. Lincoln
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
#  IN THE SOFTWARE.
#------------------------------------------------------------------------------

""" Defines a Graphviz dot language parser.

    The parser parses graphviz files dot code and files and transforms them
    into a class representation defined by Godot.

    References:
        Michael Krause, Ero Carrera, "pydot"
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

from pyparsing import __version__ as pyparsing_version

from pyparsing import \
    Literal, CaselessLiteral, Word, Upcase, OneOrMore, ZeroOrMore, Forward, \
    NotAny, delimitedList, oneOf, Group, Optional, Combine, alphas, nums, \
    restOfLine, cppStyleComment, nums, alphanums, printables, empty, \
    quotedString, ParseException, ParseResults, CharsNotIn, _noncomma, \
    dblQuotedString, QuotedString, ParserElement, Suppress, Regex, \
    removeQuotes, nestedExpr, Suppress, Or

from parsing_util import \
    colon, lbrace, rbrace, lbrack, rbrack, lparen, rparen, equals, comma, \
    dot, slash, bslash, star, semi, at, pluss, double_quoted_string, \
    quoted_string, nsplit, windows, graph_attr, node_attr, edge_attr, all_attr

import godot.graph
from godot.subgraph import Subgraph
from godot.cluster import Cluster
from godot.node import Node
from godot.edge import Edge

#------------------------------------------------------------------------------
#  "DotParser" class:
#------------------------------------------------------------------------------

class DotParser:
    """ Defines a Graphviz dot language parser.
    """

    parser = None

    graph = None

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self):
        self.parser = self.define_parser()

    #--------------------------------------------------------------------------
    #  Public interface:
    #--------------------------------------------------------------------------

    def parse_dot_file(self, file):
        """ Parses the contents of an entire file and returns a graph.
        """
        parser = self.parser

        if pyparsing_version >= "1.2":
            parser.parseWithTabs()

        tokens = parser.parseFile(file)
        return tokens[0]


    def parse_dot_data(self, data):
        """ Parses dot data and returns a godot.Graph instance.
        """
        parser = self.parser

        if pyparsing_version >= "1.2":
            parser.parseWithTabs()

#        self.graph = graph = Graph()

        tokens = parser.parseString(data)
        graph = tokens[0]

#        print "TOKENS:", tokens

        return graph

    #--------------------------------------------------------------------------
    #  Define the dot parser
    #--------------------------------------------------------------------------

    def define_parser(self):
        """ Defines dot grammar.

            @see: http://www.graphviz.org/doc/info/lang.html
        """
        # keywords
        strict_ = CaselessLiteral("strict").setResultsName("strict")
        graph_ = CaselessLiteral("graph").setResultsName("directed")
        digraph_ = CaselessLiteral("digraph").setResultsName("directed")
        subgraph_ = CaselessLiteral("subgraph").setResultsName("subgraph_")
        node_ = CaselessLiteral("node").setResultsName("node")
        edge_ = CaselessLiteral("edge").setResultsName("edge")

        # token definitions
        identifier = Word(alphanums + "_").setName("identifier")

        alphastring_ = OneOrMore(CharsNotIn(_noncomma))

        # HTML labels.
        try:
            html_text = nestedExpr(
                "<", ">", CharsNotIn("<" + ">").setParseAction(lambda t: t[0])
            ).setParseAction(lambda t: "<<%s>>" % "".join(t[0]))
        except:
            log.debug("nestedExpr not available.")
            log.warning("Old version of pyparsing detected. Version 1.4.8 or "
                "later is recommended for html label parsing.")
            html_text = Combine(Literal("<<") + OneOrMore(CharsNotIn(",]")))

        ID = (
            identifier | html_text | quoted_string | alphastring_
        ).setName("ID").setResultsName("ID")

        # Port names (node1:port1 -> node2:port5:nw;)
        port_angle = (at + ID).setName("port_angle")

        port_location = (
            (OneOrMore(Group(colon + ID)) |
            Group(colon + lparen + ID + comma + ID + rparen))
        ).setName("port_location")

        port = Combine(
            (Group(port_location + Optional(port_angle)) |
            Group(port_angle + Optional(port_location)))
        ).setName("port")

        node_id = (ID + Optional(port)).setResultsName("node_id")

        # Attribute lists.
        a_list = OneOrMore(
            Or([(CaselessLiteral(attr.resultsName) +
                Optional(equals.suppress() + attr, True) +
                Optional(comma.suppress())) for attr in all_attr])
        ).setName("a_list")

        attr_list = OneOrMore(
            lbrack.suppress() + Optional(a_list) + rbrack.suppress()
        ).setName("attr_list").setResultsName("attrlist")

        attr_stmt = ((graph_ | node_ | edge_) + attr_list).setName("attr_stmt")

        # Graph statement.
        stmt_list = Forward() # Circularity, declared later.
        graph_stmt = (Suppress(lbrace) + Optional(stmt_list) +
            Suppress(rbrace) + Optional(semi.suppress())).setName("graph_stmt")

        # Edge statement.
        edgeop = Suppress((Literal("--") | Literal("->"))).setName("edgeop")
        edge_point = Forward() # (node_id | subgraph)
        edgeRHS = OneOrMore(edgeop + edge_point)
        edge_stmt = edge_point + edgeRHS + Optional(attr_list)

        # Subgraph and cluster statements.
        subgraph = (Suppress(subgraph_) + Optional(ID, "") + #Group(graph_stmt)
            graph_stmt.setResultsName("subgraph_stmt"))

        # Connect forward declaration that required subgraph definition.
        edge_point << node_id#(subgraph | node_id)

        # Node statement.
        node_stmt = (
            node_id + Optional(attr_list) + Optional(semi.suppress())
        ).setName("node_stmt")

        # Graph attribute assignment.
        assignment = (
            Or([(CaselessLiteral(attr.resultsName) + Suppress(equals) + attr) \
                for attr in graph_attr])
        ).setResultsName("assignment")

        stmt = (
            assignment | edge_stmt | attr_stmt |
            subgraph | #graph_stmt |
            node_stmt
        ).setName("stmt")

        # Reconnect forward declaration to real definition now that stmt has
        # been defined.
        stmt_list << OneOrMore(stmt + Optional(semi.suppress()))

        # A strict graph is an unweighted, undirected graph containing no
        # graph loops or multiple edges.
        strict = Optional(strict_).setResultsName("strict")
        # Do edges have direction?
        directed = (graph_ | digraph_).setResultsName("directed")
        # Optional graph identifier.
#        graph_id = Optional(ID).setResultsName("graph_id")

        # Parser for graphs defined in the DOT language.
        graphparser = (strict + directed + Optional(ID) + Suppress(lbrace) +
            Group(Optional(stmt_list)).setResultsName("stmt_list") +
            Suppress(rbrace))

        # Ignore C++-style comments and C preprocessor output.
        preprocessorOutput = Group("#" + restOfLine)
        graphparser.ignore(preprocessorOutput)
        graphparser.ignore(cppStyleComment)

        # Parse actions.
        node_id.setParseAction(self._proc_node_id)
        assignment.setParseAction(self._proc_attr_assignment)
        a_list.setParseAction(self._proc_attr_list)
        edge_stmt.setParseAction(self._proc_edge_stmt)
        node_stmt.setParseAction(self._proc_node_stmt)
        attr_stmt.setParseAction(self._proc_default_attr_stmt)
        attr_list.setParseAction(self._proc_attr_list_combine)
        subgraph.setParseAction(self._proc_subgraph_stmt)
        #graph_stmt.setParseAction(self.push_graph_stmt)

        strict.setParseAction(self._proc_strict)
        directed.setParseAction(self._proc_directed)
#        graph_id.setParseAction(self._proc_graph_id)
        graphparser.setParseAction(self._proc_main_graph)

        return graphparser

    #--------------------------------------------------------------------------
    #  Parser actions
    #--------------------------------------------------------------------------

    def _proc_strict(self, tokens):
        """ Coerces the 'strict' token to a boolean value.
        """
        print "STRICT:", ("strict" in tokens)

        return "strict" in tokens


    def _proc_directed(self, tokens):
        """ Coerces the 'digraph' token to a boolean value.
        """
        print "DIRECTED:", tokens["directed"] == "digraph"

        return tokens["directed"] == "digraph"


    def _proc_graph_id(self, tokens):
        """ Optional graph identifier.
        """
        print "GRAPH ID:", tokens, "o", tokens["graph_id"], "o"
#        self.graph.ID = tokens["graph_id"]


    def _proc_attr_assignment(self, tokens):
        """ Sets the graph attribute to the parsed value.
        """
        print "ASSIGNMENT:", tokens, tokens.keys()
        return nsplit(tokens, 2)


    def _proc_node_id(self, tokens):
        """ Returns a tuple if more than one id exists.
        """
        print "NODE ID:", tokens, tokens.keys()

        if len(tokens) > 1:
            return (tokens[0], tokens[1]) # ID, port
        else:
            return tokens


    def _proc_attr_list(self, tokens):
        """ Splits the attributes into tuples and returns a dictionary using
            the first tuple value as the key and the second as the value.
        """
        print "ATTR LIST:", tokens
        return dict(nsplit(tokens, 2))


    def _proc_attr_list_combine(self, tokens):
        """ Combines a list of dictionaries, overwriting existing keys.
        """
        print "ATTR LIST COMBINE:", tokens

        if tokens:
            first_dict = tokens[0]
            for d in tokens:
                first_dict.update(d)
            return first_dict

        return tokens


    def _proc_node_stmt(self, tokens):
        """ Returns tuple of the form (ADD_NODE, node_name, options).
        """
        print "NODE STMT:", tokens, tokens.keys()

        graph = self.graph
        node_id = tokens["ID"]
        if isinstance(node_id, tuple):
            node_id, port = node_id

        if len(tokens) == 2:
            opts = tokens[1]
            node = Node(ID=node_id, **opts)
        else:
            node = Node(ID=node_id)

        return node


    def _proc_edge_stmt(self, tokens):
        """ Returns tuple of the form (ADD_EDGE, src, dst, options).
        """
        print "EDGE STMT:", tokens, tokens.asList(), tokens.keys()

#        graph = self.graph

        edgelist = []
        opts = tokens[-1]
        if not isinstance(opts, dict):
            opts = {}
        else:
            # Remove any attribute dictionary from the token list.
            tokens = tokens[:-1]

        for src, dst in windows(tokens, length=2, overlap=1, padding=False):
            print "WINDOW:", src, dst
            # Is src or dst a subgraph?
#            srcgraph = destgraph = False
#            if len(src) > 1 and src[0] == "add_subgraph":
#                edgelist.append(src)
#                srcgraph = True
#            if len(dest) > 1 and dest[0] == "add_subgraph":
#                edgelist.append(dest)
#                destgraph = True
#            if srcgraph or destgraph:
#                if srcgraph and destgraph:
#                    edgelist.append(
#                        ("add_graph_to_graph_edge", src[1], dest[1], opts)
#                    )
#                elif srcgraph:
#                    edgelist.append(("add_graph_head_node_edge",src[1],dest,opts))
#                else:
#                    edgelist.append(("add_node_to_graph_edge",src,dest[1],opts))
#            else:
#                # Ordinary edge
#                edgelist.append(("add_edge",src,dest,opts))

            # Ordinary edge.
            # Ports specified in the node ID take precendence over assignments.
            if isinstance(src, tuple):
                opts["tailport"] = src[1]
                src = src[0]
            if isinstance(dst, tuple):
                opts["headport"] = dst[1]
                dst = dst[0]

            # If a node didn't exist we would have to create one.
            tail_node = None#graph.get_node(src)
            if tail_node is None:
                tail_node = Node(ID=src)
#                graph.nodes.append(tail_node)
            head_node = None#graph.get_node(dst)
            if head_node is None:
                head_node = Node(ID=dst)
#                graph.nodes.append(head_node)

            edge = Edge(tail_node, head_node, **opts)
            edgelist.append(edge)

        return edgelist

#        graph.edges.extend(edgelist)

#        return tokens


    def _proc_default_attr_stmt(self, toks):
        """ If a default attribute is defined using a node, edge, or graph
            statement, or by an attribute assignment not attached to a node or
            edge, any object of the appropriate type defined afterwards will
            inherit this attribute value. This holds until the default
            attribute is set to a new value, from which point the new value is
            used.
        """
        print "DEFAULT ATTR STMT:", toks

        if len(toks)== 1:
            gtype = toks;
            attr = {}
        else:
            gtype, attr = toks
        if gtype == "node":
            return ("set_def_node_attr", attr)
        elif gtype == "edge":
            return ("set_def_edge_attr", attr)
        elif gtype == "graph":
            return ("set_def_graph_attr", attr)
        else:
            return ("unknown", toks)


    def _proc_subgraph_stmt(self, tokens):
        """ Returns a tuple of the form (ADD_SUBGRAPH, name, elements).
        """
        print "SUBGRAPH/CLUSTER:", tokens["subgraph_stmt"]

        ID = tokens["ID"]
        # Clusters are just like subgraphs, but with a 'cluster' ID prefix.
        if ID[:7].lower() == "cluster":
            subgraph = Cluster( ID = ID )
        else:
            subgraph = Subgraph( ID = ID )

        self._populate_graph( subgraph, tokens["subgraph_stmt"] )

        return subgraph


    def _proc_main_graph(self, tokens):
        """ Starts a new Graph.
        """
        print "GRAPH:", tokens, tokens.keys()

        graph = godot.graph.Graph( ID       = tokens["ID"],
                                   strict   = tokens["strict"],
                                   directed = tokens["directed"] )

        self._populate_graph( graph, elements = tokens["stmt_list"] )

        return graph


    def _populate_graph(self, graph, elements):
        """ Populates a graph, subgraph or cluster with graph elements.
        """
        for element in elements:
            if isinstance( element, Subgraph ):
                graph.subgraphs.append( element )

            elif isinstance( element, Cluster ):
                graph.clusters.append( element )

            elif isinstance( element, Node ):
                graph.nodes.append( element )

            elif isinstance( element, Edge ):
                graph.edges.append( element )

            elif isinstance( element, tuple ):
                setattr( graph, element[0], element[1] )

        return graph

#------------------------------------------------------------------------------
#  Stand-alone call:
#------------------------------------------------------------------------------

if __name__ == "__main__":
    graph_data = """digraph G {"aa\\" -> b [label="12"];}"""
    graph = DotParser().parse_dot_data(graph_data)
    graph.configure_traits()

# EOF -------------------------------------------------------------------------

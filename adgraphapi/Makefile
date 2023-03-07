all: adgraph adgraph-buildgraph
adgraph: adgraph_main.cc json_to_adgraph_parser.cc utilities.cc url.cpp adgraph.cc htmlnode.cc httpnode.cc scriptnode.cc node.cc
	g++ -std=c++11 -g -o adgraph adgraph_main.cc json_to_adgraph_parser.cc utilities.cc url.cpp adgraph.cc htmlnode.cc httpnode.cc scriptnode.cc node.cc -I.
adgraph-buildgraph: adgraph_main_buildgraph.cc json_to_adgraph_parser.cc utilities.cc url.cpp adgraph.cc htmlnode.cc httpnode.cc scriptnode.cc node.cc
	g++ -std=c++11 -g -o adgraph-buildgraph adgraph_main_buildgraph.cc json_to_adgraph_parser.cc utilities.cc url.cpp adgraph.cc htmlnode.cc httpnode.cc scriptnode.cc node.cc -I.

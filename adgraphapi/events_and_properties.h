#ifndef ADGRAPH_EVENTS_AND_PROPERTIES
#define ADGRAPH_EVENTS_AND_PROPERTIES
#include <string>

namespace AdGraphAPI{

const std::string NODE_CREATION = "NodeCreation";
const std::string NODE_INSERTION = "NodeInsertion";
const std::string NODE_REMOVAL = "NodeRemoval";
const std::string NODE_ATTACH_LATER = "NodeAttachLater";

const std::string SCRIPT_COMPILATION = "ScriptCompilation";
const std::string SCRIPT_EXECUTION = "ScriptExecution";

const std::string NETWORK_IFRAME = "NetworkIframeRequest";
const std::string NETWORK_SCRIPT = "NetworkScriptRequest";
const std::string NETWORK_IMAGE = "NetworkImageRequest";
const std::string NETWORK_LINK = "NetworkLinkRequest";
const std::string NETWORK_XMLHTTP = "NetworkXMLHTTPRequest";
const std::string NETWORK_VIDEO = "NetworkVideoRequest";

const std::string ATTR_ADDITION = "AttrAddition";
const std::string ATTR_MODIFICATION = "AttrModification";
const std::string ATTR_REMOVAL = "AttrRemoval";

const std::string ATTR_STYLE_TEXT_ADDITION = "AttrStyleTextAddition";
const std::string ATTR_STYLE_REMOVAL = "AttrStyleRemoval";
const std::string SCRIPT_EVAL = "ScriptEval";
const std::string SCRIPT_EXTENSION = "ScriptExtension";

const std::string NODE_ID = "node_id";
const std::string ACTOR_ID = "actor_id";
const std::string SCRIPT_ID = "script_id";
const std::string REQUESTOR_ID = "requestor_id";
const std::string NODE_PARENT_ID = "node_parent_id";
const std::string SCRIPT_PARENT_ID = "script_parent_id";
const std::string NODE_PREVIOUS_ID = "node_previous_sibling_id";
const std::string REQUEST_URL = "request_url";
const std::string TAG_NAME = "tag_name";
const std::string AD_CHECK = "ad_check";
const std::string NODE_TYPE = "node_type";


const std::string AD_TEXT = "AD";
const std::string NONAD_TEXT = "NONAD";

const std::string SCRIPT_TAG = "script";
const std::string EVENT_TYPE = "event_type";


const std::string NODE_TEXT = "NODE_";
const std::string SCRIPT_TEXT = "SCRIPT_";
const std::string URL_TEXT = "URL_";
// Self inserted nodes for URLs. There is a mapping between URL nodes and HTML Nodes
// Script nodes connect to the HTML node.

// FLG Images and Textnodes
const std::string ATTR_FLG_IMAGE = "flg-image";
const std::string ATTR_FLG_TEXTNODE = "flg-textnode";
const std::string ATTR_FLG_TEXTNODE_UPPER = "FLG-TEXTNODE";
const std::string ATTR_FLG_AD = "flg-ad";

// EDGE_TYPES
const std::string EDGE_TYPE_DOM = "dom";
const std::string EDGE_TYPE_ACTOR = "actor";
const std::string EDGE_TYPE_REQUESTOR = "requestor";
const std::string EDGE_TYPE_NODE_TO_SCRIPT = "node_to_script";
const std::string EDGE_TYPE_ATTACHED_LATER = "attached_later";


// Features

//Graph level features
const std::string FEATURE_GRAPH_NODES = "graph_nodes";
const std::string FEATURE_GRAPH_EDGES = "graph_edges";
const std::string FEATURE_GRAPH_NODES_EDGES = "graph_nodes_edges";
const std::string FEATURE_GRAPH_EDGES_NODES = "graph_edges_nodes";


// Parent level features
const std::string FEATURE_FIRST_PARENT_ASYNC = "first_parent_is_async";
const std::string FEATURE_FIRST_PARENT_DEFER = "first_parent_is_defer";
const std::string FEATURE_FIRST_PARENT_TAG_NAME = "first_parent_tag_name";
const std::string FEATURE_FIRST_NUMBER_OF_SIBLINGS = "first_number_of_siblings";
const std::string FEATURE_FIRST_PARENT_NUMBER_OF_SIBLINGS = "first_parent_number_of_siblings";
const std::string FEATURE_FIRST_PARENT_SIBLING_TAG_NAME = "first_parent_sibling_tag_name";
const std::string FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE = "first_parent_sibling_ad_keyword";

const std::string FEATURE_FIRST_PARENT_INBOUND_CONNECTIONS = "first_parent_inbound_connections";
const std::string FEATURE_FIRST_PARENT_OUTBOUND_CONNECTIONS = "first_parent_outbound_connections";
const std::string FEATURE_FIRST_PARENT_INBOUND_OUTBOUND_CONNECTIONS = "first_parent_inbound_outbound_connections";

const std::string FEATURE_FIRST_PARENT_NODE_ADDED_BY_SCRIPT = "first_parent_node_added_by_script";
const std::string FEATURE_FIRST_PARENT_NODE_REMOVED_BY_SCRIPT = "first_parent_node_removed_by_script";
const std::string FEATURE_FIRST_PARENT_ATTR_ADDED_BY_SCRIPT = "first_parent_attr_added_by_script";
const std::string FEATURE_FIRST_PARENT_ATTR_MODIFIED_BY_SCRIPT = "first_parent_attr_modified_by_script";
const std::string FEATURE_FIRST_PARENT_ATTR_REMOVED_BY_SCRIPT = "first_parent_attr_removed_by_script";

const std::string FEATURE_FIRST_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT = "first_parent_style_attr_added_by_script";
const std::string FEATURE_FIRST_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT = "first_parent_style_attr_removed_by_script";


const std::string FEATURE_SECOND_PARENT_ASYNC = "second_parent_is_async";
const std::string FEATURE_SECOND_PARENT_DEFER = "second_parent_is_defer";
const std::string FEATURE_SECOND_PARENT_TAG_NAME = "second_parent_tag_name";
const std::string FEATURE_SECOND_NUMBER_OF_SIBLINGS = "second_number_of_siblings";
const std::string FEATURE_SECOND_PARENT_NUMBER_OF_SIBLINGS = "second_parent_number_of_siblings";
const std::string FEATURE_SECOND_PARENT_SIBLING_TAG_NAME = "second_parent_sibling_tag_name";
const std::string FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE = "second_parent_sibling_ad_keyword";

const std::string FEATURE_SECOND_PARENT_INBOUND_CONNECTIONS = "second_parent_inbound_connections";
const std::string FEATURE_SECOND_PARENT_OUTBOUND_CONNECTIONS = "second_parent_outbound_connections";
const std::string FEATURE_SECOND_PARENT_INBOUND_OUTBOUND_CONNECTIONS = "second_parent_inbound_outbound_connections";

const std::string FEATURE_SECOND_PARENT_NODE_ADDED_BY_SCRIPT = "second_parent_node_added_by_script";
const std::string FEATURE_SECOND_PARENT_NODE_REMOVED_BY_SCRIPT = "second_parent_node_removed_by_script";
const std::string FEATURE_SECOND_PARENT_ATTR_ADDED_BY_SCRIPT = "second_parent_attr_added_by_script";
const std::string FEATURE_SECOND_PARENT_ATTR_MODIFIED_BY_SCRIPT = "second_parent_attr_modified_by_script";
const std::string FEATURE_SECOND_PARENT_ATTR_REMOVED_BY_SCRIPT = "second_parent_attr_removed_by_script";

const std::string FEATURE_SECOND_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT = "second_parent_style_attr_added_by_script";
const std::string FEATURE_SECOND_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT = "second_parent_style_attr_removed_by_script";


// Keyword level features
const std::string FEATURE_AD_KEYWORD = "ad_related_keyword";
const std::string FEATURE_SPECIAL_CHAR_AD_KEYWORD = "special_char_ad_keyword";
const std::string FEATURE_SEMICOLON_PRESENT = "semicolon_in_url";
const std::string FEATURE_VALID_QS = "valid_query_string";
const std::string FEATURE_BASE_DOMAIN_IN_QS = "base_domain_in_qs";
const std::string FEATURE_AD_DIMENSIONS_IN_QS = "ad_dimensions_in_qs";
const std::string FEATURE_AD_DIMENSIONS_IN_COMPLETE_URL = "ad_dimensions_in_complete_url";
const std::string FEATURE_SCREEN_DIMENSIONS_IN_QS = "screen_dimensions_in_qs";
const std::string FEATURE_DOMAIN_PARTY = "domain_party";
const std::string FEATURE_SUB_DOMAIN_CHECK = "sub_domain_check";
const std::string FEATURE_URL_LENGTH = "url_length";

//Ascendant level features
const std::string FEATURE_DESCENDANTS_OF_SCRIPT = "decendant_of_a_script";
const std::string FEATURE_ASCENDANTS_AD_KEYWORD = "ascendants_have_ad_keyword";
const std::string FEATURE_DESCENDANT_OF_EVAL_OR_FUNCTION = "descendant_of_eval_or_function";
const std::string FEATURE_ASCENDANT_SCRIPT_HAS_EVAL_OR_FUNCTION = "ascendant_has_eval_or_function";
const std::string FEATURE_ASCENDANT_SCRIPT_HAS_FINGERPRINTING_KEYWORD = "ascendant_has_fingerprinting_keyword";
const std::string FEATURE_ASCENDANT_SCRIPT_LENGTH = "ascendant_script_length";

// Descendants
const std::string FEATURE_DESCENDANTS = "number_of_descendants";

// Node level features
const std::string FEATURE_NODE_CATEGORY = "node_category"; // [CATEGORICAL] // iframe/script/image/link/xmlhttp
const std::string FEATURE_SCRIPT_IS_ACTIVE = "script_is_active";
const std::string FEATURE_SCRIPT_IS_EVAL_OR_FUNCTION = "script_is_eval_or_function";
const std::string FEATURE_INBOUND_CONNECTIONS = "inbound_connections";
const std::string FEATURE_OUTBOUND_CONNECTIONS = "outbound_connections";
const std::string FEATURE_INBOUND_OUTBOUND_CONNECTIONS = "inbound_outbound_connections";

// Labels
const std::string LABEL_NODE_ID = "node_id";
const std::string LABEL_NODE_CLASS = "class";

// Centrality
const std::string FEATURE_KATZ_CENTRALITY = "katz_centrality";
const std::string FEATURE_AVERAGE_DEGREE_CONNECTIVITY = "average_degree_connectivity";
const std::string FEATURE_FIRST_PARENT_KATZ_CENTRALITY = "first_parent_katz_centrality";
const std::string FEATURE_FIRST_PARENT_AVERAGE_DEGREE_CONNECTIVITY = "first_parent_average_degree_connectivity";
const std::string FEATURE_SECOND_PARENT_KATZ_CENTRALITY = "second_parent_katz_centrality";
const std::string FEATURE_SECOND_PARENT_AVERAGE_DEGREE_CONNECTIVITY = "second_parent_average_degree_connectivity";

const std::vector<std::string> KEYWORD_RAW = {"ad", "ads", "advert", "popup", "banner", "sponsor", "iframe", "googlead", "adsys", "adser", "advertise", "redirect", "popunder", "punder", "popout", "click", "track", "play", "pop", "prebid", "bid", "pb.min", "affiliate", "ban", "delivery", "promo","tag", "zoneid", "siteid", "pageid", "size", "viewid", "zone_id", "google_afc" , "google_afs"};
const std::vector<std::string> KEYWORD_CHAR = {".", "/", "&", "=", ";", "-", "_", "/", "*", "^", "?", ";", "|", ","};
const std::vector<std::string> SCREEN_RESOLUTION = {"screenheight", "screenwidth", "browserheight", "browserwidth", "screendensity", "screen_res", "screen_param", "screenresolution", "browsertimeoffset"};
const std::vector<std::string> FINGERPRINTING_KEYWORD = {"CanvasRenderingContext2D", "HTMLCanvasElement", "toDataURL", "getImageData", "measureText", "font", "fillText", "strokeText", "fillStyle", "strokeStyle", "HTMLCanvasElement.addEventListener", "save", "restore"};

} // namespace AdGraphAPI

#endif // ADGRAPH_EVENTS_AND_PROPERTIES

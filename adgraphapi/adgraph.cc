#include "adgraph.h"
#include "events_and_properties.h"
#include "url.hpp"
#include <regex>
#include <queue>


namespace AdGraphAPI
{
    AdGraph::AdGraph(std::string base_domain) :
                                        base_domain_(base_domain) {}

    std::string AdGraph::GetBaseDomain() {
        return base_domain_;
    }

    AdGraphAPI::HTMLNode* AdGraph::CreateAndReturnHTMLNode(std::string id, bool script_is_active, std::string tag_name, std::vector<std::string> attribute_name_and_values, std::string previous_sibling_id, bool async_script, bool defer_script){
        HTML_node_ids_.insert(id);
        AdGraphAPI::HTMLNode *html_node(new HTMLNode(id, script_is_active, tag_name, attribute_name_and_values, previous_sibling_id, async_script, defer_script));
        AddNode(id, html_node);

        return html_node;
    }

    AdGraphAPI::ScriptNode* AdGraph::CreateAndReturnScriptNode(std::string id, std::string script_text, bool is_eval_or_function){
        Script_node_ids_.insert(id);
        AdGraphAPI::ScriptNode *script_node(new ScriptNode(id, script_text, is_eval_or_function));
        AddNode(id, script_node);

        return script_node;
    }

    AdGraphAPI::HTTPNode* AdGraph::CreateAndReturnHTTPNode(std::string id, bool script_is_active, std::string active_script_id, std::string url, bool ad, std::string requestor_id){
        HTTP_node_ids_.insert(id);
        AdGraphAPI::HTTPNode *http_node(new HTTPNode(id, script_is_active, active_script_id, url, ad, requestor_id));
        AddNode(id, http_node);

        return http_node;
    }

    AdGraphAPI::HTTPNode* AdGraph::GetHTMLNodeToHTTPNodeMapping(AdGraphAPI::HTMLNode* html_node){
        auto node_found = HTML_HTTP_node_map_.find(html_node);
        if(node_found != HTML_HTTP_node_map_.end())
            return node_found->second;
        else
            return nullptr;
    }

    void AdGraph::AddHTMLNodeToHTTPNodeMapping(AdGraphAPI::HTMLNode* html_node, AdGraphAPI::HTTPNode* http_node){
        HTML_HTTP_node_map_[html_node] = http_node;
    }

    void AdGraph::AddAttachLaterEvent(std::string node_id, std::string parent_id){
        HTML_node_AttachLater_map_[node_id] = parent_id;
    }

    void AdGraph::AddNotAddedScript(std::string node_id){
        not_added_script_ids_.insert(node_id);
    }

    bool AdGraph::CheckIfScriptIsNotAdded(std::string node_id){
        return not_added_script_ids_.find(node_id) != not_added_script_ids_.end();
    }

    void AdGraph::RemoveAttachLaterEvent(std::string node_id){
        auto node_found = HTML_node_AttachLater_map_.find(node_id);
        if(node_found != HTML_node_AttachLater_map_.end())
            HTML_node_AttachLater_map_.erase(node_id);
    }

    void AdGraph::AddNetworkRequestAttachLaterEvent(std::string node_id, Utilities::ordered_json json_item) {
        Network_Request_AttachLater_map_[node_id] = json_item;
    }
    void AdGraph::RemoveNetworkRequestAttachLaterEvent(std::string node_id) {
        auto node_found = Network_Request_AttachLater_map_.find(node_id);
        if(node_found != Network_Request_AttachLater_map_.end())
            Network_Request_AttachLater_map_.erase(node_id);
    }

    Utilities::ordered_json AdGraph::GetNetworkRequestAttachLaterEvent(std::string node_id) {
        auto node_map = Network_Request_AttachLater_map_.find(node_id);
        if(node_map != Network_Request_AttachLater_map_.end())
            return node_map->second;
        throw std::out_of_range("Invalid node_id for NetworkRequestAttachLaterEvent: ("+node_id+")");
    }

    void AdGraph::AddNode(std::string id, AdGraphAPI::Node* node){
        node_ids_.insert(id);
        graph_[id] = node;
        katz_centrality_map_[node] = 0.0;
    }

    void AdGraph::AddEdge(std::string source_id, std::string target_id, std::string edge_type){
        edge_list_.push_back(std::make_tuple(source_id, target_id, edge_type));
    }

    AdGraphAPI::Node* AdGraph::GetAttachLaterParentNode(std::string node_id){
        auto node_map = HTML_node_AttachLater_map_.find(node_id);
        if(node_map != HTML_node_AttachLater_map_.end())
            return GetNode(node_map->second);
        else
            return nullptr;
    }

    AdGraphAPI::Node* AdGraph::GetNode(std::string id){
        auto node_found = graph_.find(id);
        if(node_found != graph_.end())
            return node_found->second;
        else
            return nullptr;
    }

    Utilities::ordered_json AdGraph::ConstructGraphPropertiesObject() {
        Utilities::ordered_json json_object;

        json_object[FEATURE_GRAPH_NODES] = 0;
        json_object[FEATURE_GRAPH_EDGES] = 0;
        json_object[FEATURE_GRAPH_NODES_EDGES] = 0.0;
        json_object[FEATURE_GRAPH_EDGES_NODES] = 0.0;

        return json_object;
    }

    Utilities::ordered_json AdGraph::ConstructFirstParentPropertiesObject(){
        Utilities::ordered_json json_object;

        json_object[FEATURE_FIRST_PARENT_ASYNC] = false;
        json_object[FEATURE_FIRST_PARENT_DEFER] = false;
        json_object[FEATURE_FIRST_PARENT_TAG_NAME] = "";
        json_object[FEATURE_FIRST_NUMBER_OF_SIBLINGS] = 0;
        json_object[FEATURE_FIRST_PARENT_NUMBER_OF_SIBLINGS] = 0;
        json_object[FEATURE_FIRST_PARENT_SIBLING_TAG_NAME] = "UNKNOWN";
        json_object[FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE] = false;

        json_object[FEATURE_FIRST_PARENT_INBOUND_CONNECTIONS] = 0;
        json_object[FEATURE_FIRST_PARENT_OUTBOUND_CONNECTIONS] = 0;
        json_object[FEATURE_FIRST_PARENT_INBOUND_OUTBOUND_CONNECTIONS] = 0;

        json_object[FEATURE_FIRST_PARENT_KATZ_CENTRALITY] = 0.0;
        json_object[FEATURE_FIRST_PARENT_AVERAGE_DEGREE_CONNECTIVITY] = 0.0;

        json_object[FEATURE_FIRST_PARENT_NODE_ADDED_BY_SCRIPT] = false;
        json_object[FEATURE_FIRST_PARENT_NODE_REMOVED_BY_SCRIPT] = false;
        json_object[FEATURE_FIRST_PARENT_ATTR_ADDED_BY_SCRIPT] = false;
        json_object[FEATURE_FIRST_PARENT_ATTR_MODIFIED_BY_SCRIPT] = false;
        json_object[FEATURE_FIRST_PARENT_ATTR_REMOVED_BY_SCRIPT] = false;

        json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT] = false;
        json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT] = false;

        return json_object;
    }

    Utilities::ordered_json AdGraph::ConstructSecondParentPropertiesObject(){
        Utilities::ordered_json json_object;

        json_object[FEATURE_SECOND_PARENT_ASYNC] = false;
        json_object[FEATURE_SECOND_PARENT_DEFER] = false;
        json_object[FEATURE_SECOND_PARENT_TAG_NAME] = "UNKNOWN";
        json_object[FEATURE_SECOND_NUMBER_OF_SIBLINGS] = 0;
        json_object[FEATURE_SECOND_PARENT_NUMBER_OF_SIBLINGS] = 0;
        json_object[FEATURE_SECOND_PARENT_SIBLING_TAG_NAME] = "UNKNOWN";
        json_object[FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE] = false;

        json_object[FEATURE_SECOND_PARENT_INBOUND_CONNECTIONS] = 0;
        json_object[FEATURE_SECOND_PARENT_OUTBOUND_CONNECTIONS] = 0;
        json_object[FEATURE_SECOND_PARENT_INBOUND_OUTBOUND_CONNECTIONS] = 0;

        json_object[FEATURE_SECOND_PARENT_KATZ_CENTRALITY] = 0.0;
        json_object[FEATURE_SECOND_PARENT_AVERAGE_DEGREE_CONNECTIVITY] = 0.0;

        json_object[FEATURE_SECOND_PARENT_NODE_ADDED_BY_SCRIPT] = false;
        json_object[FEATURE_SECOND_PARENT_NODE_REMOVED_BY_SCRIPT] = false;
        json_object[FEATURE_SECOND_PARENT_ATTR_ADDED_BY_SCRIPT] = false;
        json_object[FEATURE_SECOND_PARENT_ATTR_MODIFIED_BY_SCRIPT] = false;
        json_object[FEATURE_SECOND_PARENT_ATTR_REMOVED_BY_SCRIPT] = false;

        json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT] = false;
        json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT] = false;

        return json_object;
    }

    Utilities::ordered_json AdGraph::ConstructURLPropertiesObject(){
        Utilities::ordered_json json_object;

        json_object[FEATURE_AD_KEYWORD] = false;
        json_object[FEATURE_SPECIAL_CHAR_AD_KEYWORD] = false;
        json_object[FEATURE_VALID_QS] = false;
        json_object[FEATURE_SEMICOLON_PRESENT] = false;
        json_object[FEATURE_BASE_DOMAIN_IN_QS] = false;
        json_object[FEATURE_DOMAIN_PARTY] = false;
        json_object[FEATURE_SUB_DOMAIN_CHECK] = false;
        json_object[FEATURE_SCREEN_DIMENSIONS_IN_QS] = false;
        json_object[FEATURE_AD_DIMENSIONS_IN_QS] = false;
        json_object[FEATURE_AD_DIMENSIONS_IN_COMPLETE_URL] = false;
        json_object[FEATURE_URL_LENGTH] = 0;

        return json_object;
    }

    Utilities::ordered_json AdGraph::ConstructAscendantPropertiesObject(){
        Utilities::ordered_json json_object;

        json_object[FEATURE_DESCENDANTS_OF_SCRIPT] = false;
        json_object[FEATURE_ASCENDANTS_AD_KEYWORD] = false;
        json_object[FEATURE_DESCENDANT_OF_EVAL_OR_FUNCTION] = false;
        json_object[FEATURE_ASCENDANT_SCRIPT_HAS_EVAL_OR_FUNCTION] = false;
        json_object[FEATURE_ASCENDANT_SCRIPT_HAS_FINGERPRINTING_KEYWORD] = false;
        json_object[FEATURE_ASCENDANT_SCRIPT_LENGTH] = 0;

        return json_object;
    }

    Utilities::ordered_json AdGraph::ConstructNodePropertiesObject(){
        Utilities::ordered_json json_object;

        json_object[LABEL_NODE_ID] = "";
        json_object[FEATURE_INBOUND_CONNECTIONS] = 0;
        json_object[FEATURE_OUTBOUND_CONNECTIONS] = 0;
        json_object[FEATURE_INBOUND_OUTBOUND_CONNECTIONS] = 0;
        json_object[FEATURE_KATZ_CENTRALITY] = 0.0;
        json_object[FEATURE_AVERAGE_DEGREE_CONNECTIVITY] = 0.0;
        json_object[FEATURE_SCRIPT_IS_ACTIVE] = false;
        json_object[FEATURE_SCRIPT_IS_EVAL_OR_FUNCTION] = false;
        json_object[FEATURE_NODE_CATEGORY] = "";
        json_object[LABEL_NODE_CLASS] = "";

        return json_object;
    }

    bool AdGraph::VerifyFirstParentPropertiesObject(Utilities::ordered_json json_object){
        return json_object[FEATURE_FIRST_PARENT_ASYNC].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_DEFER].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_NODE_ADDED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_NODE_REMOVED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_ATTR_ADDED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_ATTR_MODIFIED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_ATTR_REMOVED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT].get<bool>() &&
                (json_object[FEATURE_FIRST_PARENT_TAG_NAME].get<std::string>() == "") ? false : true;
    }

    bool AdGraph::VerifySecondParentPropertiesObject(Utilities::ordered_json json_object){
        return json_object[FEATURE_SECOND_PARENT_ASYNC].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_DEFER].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_NODE_ADDED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_NODE_REMOVED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_ATTR_ADDED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_ATTR_MODIFIED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_ATTR_REMOVED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT].get<bool>() &&
                json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT].get<bool>() &&
                (json_object[FEATURE_SECOND_PARENT_TAG_NAME].get<std::string>() == "UNKNOWN") ? false : true;
    }

    std::tuple<bool, bool> AdGraph::ComputeScriptTextProperties(std::string script_text) {
        bool has_eval_or_function = false;
        bool has_fingerprinting_keyword = false;

        std::size_t eval_found = script_text.find("eval");
        if (eval_found != std::string::npos) {
            has_eval_or_function = true;
        }
        else {
            std::size_t function_found = script_text.find("Function");
            if (function_found != std::string::npos)
                has_eval_or_function = true;
        }

        for(auto &key : FINGERPRINTING_KEYWORD){
            std::size_t key_found = script_text.find(key);
            if (key_found != std::string::npos) {
                has_fingerprinting_keyword = true;
                break;
            }
        }

        return std::make_tuple(has_eval_or_function, has_fingerprinting_keyword);
    }

    Utilities::ordered_json AdGraph::GetFirstParentProperties(AdGraphAPI::HTTPNode* http_node){
        Utilities::ordered_json json_object = ConstructFirstParentPropertiesObject();

        if(http_node->GetInboundEdgeCount() == 0)
            return json_object;

        AdGraphAPI::Node *node_first_parent = http_node->GetParents().at(0);
        AdGraphAPI::HTMLNode *html_first_parnet_node = dynamic_cast<AdGraphAPI::HTMLNode*>(node_first_parent);

        if (html_first_parnet_node != nullptr){

            if (json_object[FEATURE_FIRST_PARENT_ASYNC] == false)
                    json_object[FEATURE_FIRST_PARENT_ASYNC] = html_first_parnet_node->GetAsyncStatus();

            if (json_object[FEATURE_FIRST_PARENT_DEFER] == false)
                    json_object[FEATURE_FIRST_PARENT_DEFER] = html_first_parnet_node->GetDeferStatus();

            json_object[FEATURE_FIRST_PARENT_INBOUND_CONNECTIONS] = json_object[FEATURE_FIRST_PARENT_INBOUND_CONNECTIONS].get<int>() + html_first_parnet_node->GetInboundEdgeCount();
            json_object[FEATURE_FIRST_PARENT_OUTBOUND_CONNECTIONS] = json_object[FEATURE_FIRST_PARENT_OUTBOUND_CONNECTIONS].get<int>() + html_first_parnet_node->GetOutboundEdgeCount();
            json_object[FEATURE_FIRST_PARENT_INBOUND_OUTBOUND_CONNECTIONS] = json_object[FEATURE_FIRST_PARENT_INBOUND_CONNECTIONS].get<int>() + json_object[FEATURE_FIRST_PARENT_OUTBOUND_CONNECTIONS].get<int>();

            json_object[FEATURE_FIRST_NUMBER_OF_SIBLINGS] = json_object[FEATURE_FIRST_NUMBER_OF_SIBLINGS].get<int>() + html_first_parnet_node->GetOutboundEdgeCount();


            AdGraphAPI::HTMLNode *html_first_parnet_sibling = dynamic_cast<AdGraphAPI::HTMLNode*>(GetNode(NODE_TEXT + html_first_parnet_node->GetPreviousSiblingId()));

            if(html_first_parnet_sibling) {
                json_object[FEATURE_FIRST_PARENT_SIBLING_TAG_NAME] = html_first_parnet_sibling->GetTagName();
                if(html_first_parnet_sibling->GetIsAdKeywordComputed()){
                    json_object[FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE] = html_first_parnet_sibling->GetHasAdKeyword();
                }
                else{
                    std::vector<std::string> attr_vector = html_first_parnet_sibling->GetAttributeNameAndValues();

                    for (auto &key_to_match : KEYWORD_RAW) {
                        for(auto &attr : attr_vector){
                            std::size_t key_found = attr.find(key_to_match);
                            if (key_found != std::string::npos) {
                                json_object[FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE] = true;
                                html_first_parnet_sibling->SetIsAdKeywordComputed(true);
                                html_first_parnet_sibling->SetHasAdKeyword(true);
                                break;
                            }
                        }
                        if(json_object[FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE] != true)
                            break;
                    }
                    html_first_parnet_sibling->SetIsAdKeywordComputed(true);
                    if(json_object[FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE] == false)
                        html_first_parnet_sibling->SetHasAdKeyword(false);
                }
            }


            json_object[FEATURE_FIRST_PARENT_KATZ_CENTRALITY] = katz_centrality_map_[node_first_parent];
            json_object[FEATURE_FIRST_PARENT_AVERAGE_DEGREE_CONNECTIVITY] = GetAverageDegreeConnectivity(node_first_parent);

            for(AdGraphAPI::Node *node_parent : node_first_parent->GetParents()) {
                AdGraphAPI::HTMLNode *html_node = dynamic_cast<AdGraphAPI::HTMLNode*>(node_parent);

                if (html_node != nullptr){
                    if (json_object[FEATURE_FIRST_PARENT_TAG_NAME] == "")
                        json_object[FEATURE_FIRST_PARENT_TAG_NAME] = html_node->GetTagName();

                    if(json_object[FEATURE_FIRST_PARENT_NODE_ADDED_BY_SCRIPT] == false)
                        json_object[FEATURE_FIRST_PARENT_NODE_ADDED_BY_SCRIPT] = html_node->GetNodeInsertionWithScriptStatus();

                    if(json_object[FEATURE_FIRST_PARENT_NODE_REMOVED_BY_SCRIPT] == false)
                        json_object[FEATURE_FIRST_PARENT_NODE_REMOVED_BY_SCRIPT] = html_node->GetNodeRemovalWithScriptStatus();

                    if(json_object[FEATURE_FIRST_PARENT_ATTR_ADDED_BY_SCRIPT] == false)
                        json_object[FEATURE_FIRST_PARENT_ATTR_ADDED_BY_SCRIPT] = html_node->GetAttributeAdditionWithScriptStatus();

                    if(json_object[FEATURE_FIRST_PARENT_ATTR_MODIFIED_BY_SCRIPT] == false)
                        json_object[FEATURE_FIRST_PARENT_ATTR_MODIFIED_BY_SCRIPT] = html_node->GetAttributeModificationWithScriptStatus();

                    if(json_object[FEATURE_FIRST_PARENT_ATTR_REMOVED_BY_SCRIPT] == false)
                        json_object[FEATURE_FIRST_PARENT_ATTR_REMOVED_BY_SCRIPT] = html_node->GetAttributeRemovalWithScriptStatus();

                    if(json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT] == false)
                        json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT] = html_node->GetAttributeStyleAdditionWithScriptStatus();

                    if(json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT] == false)
                        json_object[FEATURE_FIRST_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT] = html_node->GetAttributeStyleRemovalWithScriptStatus();

                    json_object[FEATURE_FIRST_PARENT_NUMBER_OF_SIBLINGS] = json_object[FEATURE_FIRST_PARENT_NUMBER_OF_SIBLINGS].get<int>() + html_node->GetOutboundEdgeCount();
                }
                if (VerifyFirstParentPropertiesObject(json_object))
                    return json_object;
            }
        }
        return json_object;
    }

    Utilities::ordered_json AdGraph::GetSecondParentProperties(AdGraphAPI::HTTPNode* http_node){
        Utilities::ordered_json json_object = ConstructSecondParentPropertiesObject();

        if(http_node->GetInboundEdgeCount() < 2)
            return json_object;

        AdGraphAPI::Node *node_second_parent = http_node->GetParents().at(1);
        AdGraphAPI::HTMLNode *html_second_parnet_node = dynamic_cast<AdGraphAPI::HTMLNode*>(node_second_parent);

        if (html_second_parnet_node != nullptr){

            if (json_object[FEATURE_SECOND_PARENT_ASYNC] == false)
                    json_object[FEATURE_SECOND_PARENT_ASYNC] = html_second_parnet_node->GetAsyncStatus();

            if (json_object[FEATURE_SECOND_PARENT_DEFER] == false)
                    json_object[FEATURE_SECOND_PARENT_DEFER] = html_second_parnet_node->GetDeferStatus();

            json_object[FEATURE_SECOND_PARENT_INBOUND_CONNECTIONS] = json_object[FEATURE_SECOND_PARENT_INBOUND_CONNECTIONS].get<int>() + html_second_parnet_node->GetInboundEdgeCount();
            json_object[FEATURE_SECOND_PARENT_OUTBOUND_CONNECTIONS] = json_object[FEATURE_SECOND_PARENT_OUTBOUND_CONNECTIONS].get<int>() + html_second_parnet_node->GetOutboundEdgeCount();
            json_object[FEATURE_SECOND_PARENT_INBOUND_OUTBOUND_CONNECTIONS] = json_object[FEATURE_SECOND_PARENT_INBOUND_CONNECTIONS].get<int>() + json_object[FEATURE_SECOND_PARENT_OUTBOUND_CONNECTIONS].get<int>();

            json_object[FEATURE_SECOND_NUMBER_OF_SIBLINGS] = json_object[FEATURE_SECOND_NUMBER_OF_SIBLINGS].get<int>() + html_second_parnet_node->GetOutboundEdgeCount();

            AdGraphAPI::HTMLNode *html_second_parnet_sibling = dynamic_cast<AdGraphAPI::HTMLNode*>(GetNode(NODE_TEXT + html_second_parnet_node->GetPreviousSiblingId()));

            if(html_second_parnet_sibling) {
                json_object[FEATURE_SECOND_PARENT_SIBLING_TAG_NAME] = html_second_parnet_sibling->GetTagName();
                if(html_second_parnet_sibling->GetIsAdKeywordComputed()){
                    json_object[FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE] = html_second_parnet_sibling->GetHasAdKeyword();
                }
                else{
                    std::vector<std::string> attr_vector = html_second_parnet_sibling->GetAttributeNameAndValues();

                    for (auto &key_to_match : KEYWORD_RAW) {
                        for(auto &attr : attr_vector){
                            std::size_t key_found = attr.find(key_to_match);
                            if (key_found != std::string::npos) {
                                json_object[FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE] = true;
                                html_second_parnet_sibling->SetIsAdKeywordComputed(true);
                                html_second_parnet_sibling->SetHasAdKeyword(true);
                                break;
                            }
                        }
                        if(json_object[FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE] == true)
                            break;
                    }
                    html_second_parnet_sibling->SetIsAdKeywordComputed(true);
                    if(json_object[FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE] == false)
                        html_second_parnet_sibling->SetHasAdKeyword(false);
                }
            }

            json_object[FEATURE_SECOND_PARENT_KATZ_CENTRALITY] = katz_centrality_map_[node_second_parent];
            json_object[FEATURE_SECOND_PARENT_AVERAGE_DEGREE_CONNECTIVITY] = GetAverageDegreeConnectivity(node_second_parent);

            for(AdGraphAPI::Node *node_parent : node_second_parent->GetParents()) {
                AdGraphAPI::HTMLNode *html_node = dynamic_cast<AdGraphAPI::HTMLNode*>(node_parent);

                if (html_node != nullptr){
                    if (json_object[FEATURE_SECOND_PARENT_TAG_NAME] == "UNKNOWN")
                        json_object[FEATURE_SECOND_PARENT_TAG_NAME] = html_node->GetTagName();

                    if(json_object[FEATURE_SECOND_PARENT_NODE_ADDED_BY_SCRIPT] == false)
                        json_object[FEATURE_SECOND_PARENT_NODE_ADDED_BY_SCRIPT] = html_node->GetNodeInsertionWithScriptStatus();

                    if(json_object[FEATURE_SECOND_PARENT_NODE_REMOVED_BY_SCRIPT] == false)
                        json_object[FEATURE_SECOND_PARENT_NODE_REMOVED_BY_SCRIPT] = html_node->GetNodeRemovalWithScriptStatus();

                    if(json_object[FEATURE_SECOND_PARENT_ATTR_ADDED_BY_SCRIPT] == false)
                        json_object[FEATURE_SECOND_PARENT_ATTR_ADDED_BY_SCRIPT] = html_node->GetAttributeAdditionWithScriptStatus();

                    if(json_object[FEATURE_SECOND_PARENT_ATTR_MODIFIED_BY_SCRIPT] == false)
                        json_object[FEATURE_SECOND_PARENT_ATTR_MODIFIED_BY_SCRIPT] = html_node->GetAttributeModificationWithScriptStatus();

                    if(json_object[FEATURE_SECOND_PARENT_ATTR_REMOVED_BY_SCRIPT] == false)
                        json_object[FEATURE_SECOND_PARENT_ATTR_REMOVED_BY_SCRIPT] = html_node->GetAttributeRemovalWithScriptStatus();

                    if(json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT] == false)
                        json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT] = html_node->GetAttributeStyleAdditionWithScriptStatus();

                    if(json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT] == false)
                        json_object[FEATURE_SECOND_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT] = html_node->GetAttributeStyleRemovalWithScriptStatus();

                    json_object[FEATURE_SECOND_PARENT_NUMBER_OF_SIBLINGS] = json_object[FEATURE_SECOND_PARENT_NUMBER_OF_SIBLINGS].get<int>() + html_node->GetOutboundEdgeCount();
                }
                if (VerifySecondParentPropertiesObject(json_object))
                    return json_object;
            }
        }
        return json_object;
    }

    Utilities::ordered_json AdGraph::GetGraphProperties(){
        Utilities::ordered_json json_object = ConstructGraphPropertiesObject();

        json_object[FEATURE_GRAPH_NODES] = node_ids_.size();
        json_object[FEATURE_GRAPH_EDGES] = edge_list_.size();
        json_object[FEATURE_GRAPH_NODES_EDGES] = std::abs(double(node_ids_.size())/double(edge_list_.size()));
        json_object[FEATURE_GRAPH_EDGES_NODES] = std::abs(double(edge_list_.size())/double(node_ids_.size()));

        return json_object;
    }

    Utilities::ordered_json AdGraph::GetURLProperties(AdGraphAPI::HTTPNode* http_node) {
        Utilities::ordered_json json_object = ConstructURLPropertiesObject();
        std::string node_url = http_node->GetURL();

        json_object[FEATURE_URL_LENGTH] = node_url.length();

        // count keyword and keyword followed by char
        for (auto &key_to_match : KEYWORD_RAW)
        {
            std::size_t key_found = node_url.find(key_to_match);
            while (key_found != std::string::npos)
            {
                json_object[FEATURE_AD_KEYWORD] = true;
                if ((key_found != 0) && (std::find(KEYWORD_CHAR.begin(), KEYWORD_CHAR.end(), std::string(1, node_url[key_found - 1])) != KEYWORD_CHAR.end()))
                {
                    json_object[FEATURE_SPECIAL_CHAR_AD_KEYWORD] = true;
                    break;
                }
                key_found = node_url.find(key_to_match, key_found + 1);
            }
            if (json_object[FEATURE_SPECIAL_CHAR_AD_KEYWORD].get<bool>())
                break;
        }

        // check valid query string and semicolon
        Url::Query query_string;
        std::string parsed_url_host = "";

        try {
            Url parsed_url(node_url);
            query_string = parsed_url.query();
            parsed_url_host = parsed_url.host();
        } catch (const std::exception &e){
            // std::cout << "\nException while parsing URL: " << e.what() << std::endl;
            query_string = {};
            parsed_url_host = "";
        } catch (...) {
            // std::cout << "\nException while parsing URL: " << e.what() << std::endl;
            query_string = {};
            parsed_url_host = "";
        }

        if (query_string.empty())
            json_object[FEATURE_VALID_QS] = true;

        std::size_t semicolon_index = node_url.find(";");
        if (semicolon_index != std::string::npos)
            json_object[FEATURE_SEMICOLON_PRESENT] = true;


        // check base domain in qs
        std::string domain_name = "";
        try {
            Url parsed_base_domain(base_domain_);
            domain_name = parsed_base_domain.host();
        } catch (const std::exception &e){
            // std::cout << "\nException while parsing URL: " << e.what() << std::endl;
            domain_name = "";
        } catch (...) {
            // std::cout << "\nException while parsing URL: " << e.what() << std::endl;
            domain_name = "";
        }

        std::string www = "www.";
        if (strncmp(domain_name.c_str(), www.c_str(), www.size()) == 0)
            domain_name.erase(0, 4);


        for (const auto &param : query_string)
        {
            std::size_t base_domain_index = param.val().find(domain_name);
            if (base_domain_index != std::string::npos){
                json_object[FEATURE_BASE_DOMAIN_IN_QS] = true;
                break;
            }
        }

        //check third party
        if (strncmp(parsed_url_host.c_str(), www.c_str(), www.size()) == 0)
            parsed_url_host.erase(0, 4);

        if (domain_name == parsed_url_host)
            json_object[FEATURE_DOMAIN_PARTY] = true;

        // Hack for sub domain:check for better mehtod in KURL.
        std::size_t sub_donain_check = parsed_url_host.find(domain_name);
        if (sub_donain_check != std::string::npos)
            json_object[FEATURE_SUB_DOMAIN_CHECK] = true;

        // matching size and dimensions
        std::regex regex_expr("\\d{2,4}[xX_-]\\d{2,4}");
        // std::regex regex_expr("(.*?)\\d{2,4}[xX_-]\\d{2,4}(.*?)");
        for (auto &screen_key : SCREEN_RESOLUTION)
        {
            for (const auto &param : query_string)
            {
                std::size_t screen_key_found = param.key().find(screen_key);

                if (std::regex_search(param.val(), regex_expr))
                    json_object[FEATURE_AD_DIMENSIONS_IN_QS] = true;

                if (screen_key_found != std::string::npos)
                    json_object[FEATURE_SCREEN_DIMENSIONS_IN_QS] = true;

                if (json_object[FEATURE_AD_DIMENSIONS_IN_QS].get<bool>() && json_object[FEATURE_SCREEN_DIMENSIONS_IN_QS].get<bool>() )
                    break;
            }
            if (json_object[FEATURE_AD_DIMENSIONS_IN_QS].get<bool>()  && json_object[FEATURE_SCREEN_DIMENSIONS_IN_QS].get<bool>() )
                break;
        }

        // check ad dimmension in invalid querystring too.
        if (std::regex_search(node_url, regex_expr))
            json_object[FEATURE_AD_DIMENSIONS_IN_COMPLETE_URL] = true;

        return json_object;
    }


    Utilities::ordered_json AdGraph::GetAscendantProperties(AdGraphAPI::HTTPNode* http_node, int level) {
        Utilities::ordered_json json_object = ConstructAscendantPropertiesObject();
        std::queue<AdGraphAPI::Node*> node_queue;
        node_queue.push(http_node);

        while(level > 0 && node_queue.size() > 0) {
            for(AdGraphAPI::Node *node_parent : node_queue.front()->GetParents()) {
                level -= 1;
                node_queue.push(node_parent);
                AdGraphAPI::HTMLNode *html_node = dynamic_cast<AdGraphAPI::HTMLNode*>(node_parent);

                if (html_node != nullptr){
                    std::string node_tag_name = html_node->GetTagName();
                    if(node_tag_name == "SCRIPT" ||node_tag_name == "script")
                        json_object[FEATURE_DESCENDANTS_OF_SCRIPT] = true;

                    if (!html_node->GetIsAdKeywordComputed()){
                        std::vector<std::string> attr_vector = html_node->GetAttributeNameAndValues();

                        for (auto &key_to_match : KEYWORD_RAW) {
                            for(auto &attr : attr_vector){
                                std::size_t key_found = attr.find(key_to_match);
                                if (key_found != std::string::npos) {
                                    json_object[FEATURE_ASCENDANTS_AD_KEYWORD] = true;
                                    html_node->SetIsAdKeywordComputed(true);
                                    html_node->SetHasAdKeyword(true);
                                    break;
                                }
                            }
                            if(json_object[FEATURE_ASCENDANTS_AD_KEYWORD] == true)
                                break;
                        }
                        html_node->SetIsAdKeywordComputed(true);
                        if(json_object[FEATURE_ASCENDANTS_AD_KEYWORD] == false)
                            html_node->SetHasAdKeyword(false);
                    }
                    else {
                        if(html_node->GetHasAdKeyword())
                            json_object[FEATURE_ASCENDANTS_AD_KEYWORD] = true;
                    }
                }

                AdGraphAPI::ScriptNode *script_node = dynamic_cast<AdGraphAPI::ScriptNode*>(node_parent);
                if (script_node != nullptr){
                    json_object[FEATURE_DESCENDANTS_OF_SCRIPT] = true;
                    json_object[FEATURE_DESCENDANT_OF_EVAL_OR_FUNCTION] = script_node->GetIsEvalOrFunction();
                    if(script_node->GetScriptPropertiesComputedStatus()){
                        json_object[FEATURE_ASCENDANT_SCRIPT_HAS_EVAL_OR_FUNCTION] = script_node->HasEvalOrFunction();
                        json_object[FEATURE_ASCENDANT_SCRIPT_HAS_FINGERPRINTING_KEYWORD] = script_node->HasFingerprintingKeyword();
                        json_object[FEATURE_ASCENDANT_SCRIPT_LENGTH] = script_node->GetScriptLength();
                    }
                    else{
                        std::string script_text = script_node->GetScriptText();
                        auto properties_tuple = ComputeScriptTextProperties(script_text);

                        json_object[FEATURE_ASCENDANT_SCRIPT_HAS_EVAL_OR_FUNCTION] = std::get<0>(properties_tuple);
                        json_object[FEATURE_ASCENDANT_SCRIPT_HAS_FINGERPRINTING_KEYWORD] = std::get<1>(properties_tuple);
                        json_object[FEATURE_ASCENDANT_SCRIPT_LENGTH] = script_node->GetScriptLength();

                        script_node->SetScriptPropertiesComputedStatus(true);
                        script_node->SetEvalOrFunction(std::get<0>(properties_tuple));
                        script_node->SetFingerprintingKeyword(std::get<1>(properties_tuple));
                    }
                }

                if(json_object[FEATURE_DESCENDANTS_OF_SCRIPT] == true && json_object[FEATURE_ASCENDANTS_AD_KEYWORD] == true)
                    return json_object;
            }
            node_queue.pop();
        }
        return json_object;
    }

    Utilities::ordered_json AdGraph::GetNumberOfDescendants(AdGraphAPI::HTTPNode* http_node, int level) {
        Utilities::ordered_json json_object;
        json_object[FEATURE_DESCENDANTS] = 0;

        std::queue<AdGraphAPI::Node*> node_queue;
        node_queue.push(http_node);

        while(level > 0 && node_queue.size() > 0) {
            for(AdGraphAPI::Node *node_child : node_queue.front()->GetChilden()) {
                level -= 1;
                node_queue.push(node_child);
                json_object[FEATURE_DESCENDANTS] = json_object[FEATURE_DESCENDANTS].get<int>() + 1;
            }
            node_queue.pop();
        }
        return json_object;
    }

    Utilities::ordered_json AdGraph::GetNodeProperties(AdGraphAPI::HTTPNode* http_node, std::string event_type){
        Utilities::ordered_json json_object =  ConstructNodePropertiesObject();

        json_object[LABEL_NODE_ID] = http_node->GetId();
        json_object[FEATURE_INBOUND_CONNECTIONS] = http_node->GetInboundEdgeCount();
        json_object[FEATURE_OUTBOUND_CONNECTIONS] = http_node->GetOutboundEdgeCount();
        json_object[FEATURE_INBOUND_OUTBOUND_CONNECTIONS] = json_object[FEATURE_INBOUND_CONNECTIONS].get<int>() + json_object[FEATURE_OUTBOUND_CONNECTIONS].get<int>();
        json_object[FEATURE_KATZ_CENTRALITY] = katz_centrality_map_[http_node];
        json_object[FEATURE_AVERAGE_DEGREE_CONNECTIVITY] = GetAverageDegreeConnectivity(http_node);
        json_object[FEATURE_SCRIPT_IS_ACTIVE] = http_node->GetScriptIsActiveStatus();

        AdGraphAPI::ScriptNode *script_node = dynamic_cast<AdGraphAPI::ScriptNode*>(GetNode(SCRIPT_TEXT + http_node->GetActiveScriptId()));
        if(script_node)
            json_object[FEATURE_SCRIPT_IS_EVAL_OR_FUNCTION] = script_node->GetIsEvalOrFunction();

        json_object[FEATURE_NODE_CATEGORY] = event_type;
        json_object[LABEL_NODE_CLASS] = (http_node->GetAd() == true) ? AD_TEXT : NONAD_TEXT;

        return json_object;
    }

    Utilities::ordered_json AdGraph::GetAllProperties(AdGraphAPI::HTTPNode* http_node, std::string event_type, int ascendant_level, int descendant_level){
        Utilities::ordered_json all_properties;

        Utilities::uint64 start_time = 0;

        start_time = AdGraphAPI::Utilities::GetTimeMs64();
        UpdateKatzCentrality();
        timing_vector_[6] += AdGraphAPI::Utilities::GetTimeMs64() - start_time;

        Utilities::ordered_json graph_properties = GetGraphProperties();

        start_time = AdGraphAPI::Utilities::GetTimeMs64();
        Utilities::ordered_json node_properties = GetNodeProperties(http_node, event_type);
        timing_vector_[0] += AdGraphAPI::Utilities::GetTimeMs64() - start_time;

        start_time = AdGraphAPI::Utilities::GetTimeMs64();
        Utilities::ordered_json first_parent_properties = GetFirstParentProperties(http_node);
        timing_vector_[1] += AdGraphAPI::Utilities::GetTimeMs64() - start_time;

        start_time = AdGraphAPI::Utilities::GetTimeMs64();
        Utilities::ordered_json second_parent_properties = GetSecondParentProperties(http_node);
        timing_vector_[2] += AdGraphAPI::Utilities::GetTimeMs64() - start_time;

        start_time = AdGraphAPI::Utilities::GetTimeMs64();
        Utilities::ordered_json url_properties = GetURLProperties(http_node);
        timing_vector_[3] += AdGraphAPI::Utilities::GetTimeMs64() - start_time;

        start_time = AdGraphAPI::Utilities::GetTimeMs64();
        Utilities::ordered_json ascendant_properties = GetAscendantProperties(http_node, ascendant_level);
        timing_vector_[4] += AdGraphAPI::Utilities::GetTimeMs64() - start_time;

        start_time = AdGraphAPI::Utilities::GetTimeMs64();
        Utilities::ordered_json descendant_properties = GetNumberOfDescendants(http_node, descendant_level);
        timing_vector_[5] += AdGraphAPI::Utilities::GetTimeMs64() - start_time;

        all_properties.update(graph_properties);
        all_properties.update(node_properties);
        all_properties.update(first_parent_properties);
        all_properties.update(second_parent_properties);
        all_properties.update(url_properties);
        all_properties.update(ascendant_properties);
        all_properties.update(descendant_properties);

        // std::cout << timing_vector_[0] << " , " << timing_vector_[1] << " , " << timing_vector_[2] << " , " << timing_vector_[3] << " , " << timing_vector_[4] << " , " << timing_vector_[5] << " , " << timing_vector_[6] << std::endl;

        return all_properties;
    }


    void AdGraph::UpdateKatzCentrality(double alpha, double beta, int max_iter, double tol) {
        // Replicated implementation from NetworkX.
        // https://networkx.github.io/documentation/stable/_modules/networkx/algorithms/centrality/katz.html

        std::map<AdGraphAPI::Node*, double> last_valid_katz_centrality_map_(katz_centrality_map_);
        bool converged = false;

        for (int i = 0; i < max_iter; i++) {
            std::map<AdGraphAPI::Node*, double> previous_node_centralities(katz_centrality_map_);

            for (auto& item : katz_centrality_map_) {
                item.second = 0.0;
            }

            for (auto& node : katz_centrality_map_) {
                for(auto& parent : node.first->GetParents()){
                    katz_centrality_map_[parent] += previous_node_centralities[node.first];
                }
            }

            for (auto& node : katz_centrality_map_) {
                katz_centrality_map_[node.first] = alpha * katz_centrality_map_[node.first] + beta;
            }

            // Convergence checking
            double error = 0.0;
            double sum = 0.0;
            for (const auto& node : katz_centrality_map_) {
                error += std::abs(katz_centrality_map_[node.first] - previous_node_centralities[node.first]);
                sum += std::pow(node.second, 2);
            }

            if (error < node_ids_.size() * tol){
                // If converged, we normalize centrality values and return them.
                double normalization_factor = 1.0 / std::sqrt(sum);
                for (auto& node : katz_centrality_map_) {
                    node.second *= normalization_factor * 1000;
                    // 1000 is my modification, need to validate this.
                }
                converged = true;
                break;
            }
        } // end for loop, max iterations

        if(!converged){
            // When the centrality values are not converged.
            // We reinitialize to last valid centrality values.
            for (auto& item : katz_centrality_map_) {
                item.second = last_valid_katz_centrality_map_[item.first];
            }
        }
        // This loop is used to print centrality values.
        // It should be removed after complete testing.
        // for (auto& node : katz_centrality_map_) {
        //     std::cout << node.second << std::endl;
        // }
    }

    double AdGraph::GetAverageDegreeConnectivity(AdGraphAPI::Node* node) {
        double neighbor_degree_sum = 0.0;
        double node_degree = node->GetInboundEdgeCount() + node->GetOutboundEdgeCount();

        for(auto *node_parent : node->GetParents()) {
            neighbor_degree_sum += node_parent->GetInboundEdgeCount() + node_parent->GetOutboundEdgeCount();
        }

        for(auto *node_child : node->GetChilden()) {
            neighbor_degree_sum += node_child->GetInboundEdgeCount() + node_child->GetOutboundEdgeCount();
        }

        double max_degree = 0.0;

        // We can choose maximum node degree to be the normalization factor.
        for(const auto& item : graph_) {
            double temp_degree = item.second->GetInboundEdgeCount() + item.second->GetOutboundEdgeCount();
            if(temp_degree > max_degree)
                max_degree = temp_degree;
        }
        // We can choose maximum possible degree; total number of nodes to be normalization factor.
        // double normalization_factor = node_ids_.size();

        return (neighbor_degree_sum/node_degree)/max_degree;
    }

    Utilities::ordered_json AdGraph::GetTimingInfo(){
        Utilities::ordered_json json_object;

        json_object["nodes"] = node_ids_.size();
        json_object["edges"] = edge_list_.size();
        json_object["url_nodes"] = HTTP_node_ids_.size();

        json_object["node_properties"] = timing_vector_[0];
        json_object["first_parent_properties"] = timing_vector_[1];
        json_object["second_parent_properties"] = timing_vector_[2];
        json_object["url_properties"] = timing_vector_[3];
        json_object["ascendant_properties"] = timing_vector_[4];
        json_object["descendant_properties"] = timing_vector_[5];
        json_object["katz_properties"] = timing_vector_[6];

        return json_object;
    }

    Utilities::ordered_json AdGraph::PrepareJSONVisualization(){
        // HTML_GROUP_VAL = 1
        // IMAGE_GROUP_VAL = 2
        // IFRAME_GROUP_VAL = 4
        // IFRAMEURL_GROUP_VAL = 5
        // HTTP_GROUP_VAL = 6
        // SCRIPT_GROUP_VAL = 7
        // STYLE_GROUP_VAL = 8
        // ELEMENTURL_GROUP_VAL = 9
        // SCRIPTURL_GROUP_VAL = 0

        Utilities::ordered_json json_graph;

        json_graph["nodes"] = Utilities::ordered_json::array();
        json_graph["links"] = Utilities::ordered_json::array();

        for(const auto& edge : edge_list_) {
            Utilities::ordered_json json_obj = Utilities::ordered_json::object();
            json_obj["source"] = std::get<0>(edge);
            json_obj["target"] = std::get<1>(edge);
            json_obj["edge_type"] = std::get<2>(edge);
            json_graph["links"].push_back(json_obj);
        }

        for(const auto& node : graph_) {
            Utilities::ordered_json json_obj = Utilities::ordered_json::object();
            json_obj["id"] = node.second->GetId();
            json_obj["connections"] = node.second->GetInboundEdgeCount() + node.second->GetOutboundEdgeCount();

            AdGraphAPI::HTMLNode *current_node_is_html = dynamic_cast<AdGraphAPI::HTMLNode*>(node.second);
            AdGraphAPI::ScriptNode *current_node_is_script = dynamic_cast<AdGraphAPI::ScriptNode*>(node.second);
            AdGraphAPI::HTTPNode *current_node_is_http = dynamic_cast<AdGraphAPI::HTTPNode*>(node.second);

            // std::cout <<  node.second->GetId() << std::endl;
            if(current_node_is_html != nullptr) {
                // std::cout <<  node.second->GetId() << " , " << current_node_is_html->GetTagName() << std::endl;
                std::string temp_tag_name = current_node_is_html->GetTagName();
                json_obj["info"] = temp_tag_name;
                //json_obj["ad"] = NONAD_TEXT;
                json_obj["flg-image"] = (current_node_is_html->GetIsFLGImage() == true) ? "true" : "false";
                json_obj["flg-textnode"] = (current_node_is_html->GetIsFLGTextnode() == true) ? "true" : "false";
                json_obj["flg-ad"] = (current_node_is_html->GetIsFLGAd() == true) ? "true" : "false";

                json_obj["requested_url"] = current_node_is_html->GetRequestedUrl();

                if(temp_tag_name == "IMG" || temp_tag_name == "img")
                    json_obj["group"] = 2;
                else if(temp_tag_name == "IFRAME" || temp_tag_name == "iframe")
                    json_obj["group"] = 4;
                else if(temp_tag_name == "LINK" || temp_tag_name == "link")
                    json_obj["group"] = 8;
                else
                    json_obj["group"] = 1;
            }

            else if (current_node_is_script != nullptr){
                json_obj["info"] = SCRIPT_TAG;
                //json_obj["ad"] = NONAD_TEXT;
                json_obj["group"] = 7;
            }

            else if (current_node_is_http != nullptr){
                json_obj["info"] = current_node_is_http->GetURL();
                //json_obj["ad"] =  (current_node_is_http->GetAd() == true) ? AD_TEXT : NONAD_TEXT;
                json_obj["group"] = 6;
            }
            json_graph["nodes"].push_back(json_obj);
        }
        return json_graph;
    }

} // namespace AdGraphAPI



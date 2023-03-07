#ifndef ADGRAPH
#define ADGRAPH
#include <string>
#include <set>
#include <map>
#include <vector>
#include "node.h"
#include "htmlnode.h"
#include "httpnode.h"
#include "scriptnode.h"


namespace AdGraphAPI
{

class AdGraph
{
  public:
    AdGraph(std::string base_domain);
    std::string GetBaseDomain();

    AdGraphAPI::HTMLNode* CreateAndReturnHTMLNode(std::string id, bool script_is_active, std::string tag_name, std::vector<std::string> attribute_name_and_values, std::string previous_sibling_id, bool async_script, bool defer_script);
    AdGraphAPI::ScriptNode* CreateAndReturnScriptNode(std::string id, std::string script_text, bool is_eval_or_function);
    AdGraphAPI::HTTPNode* CreateAndReturnHTTPNode(std::string id, bool script_is_active, std::string active_script_id, std::string url, bool ad, std::string requestor_id);

    AdGraphAPI::Node* GetNode(std::string id);
    void AddEdge(std::string source_id, std::string target_id, std::string edge_type);

    AdGraphAPI::HTTPNode* GetHTMLNodeToHTTPNodeMapping(AdGraphAPI::HTMLNode* html_node);
    void AddHTMLNodeToHTTPNodeMapping(AdGraphAPI::HTMLNode* html_node, AdGraphAPI::HTTPNode* http_node);
    void AddAttachLaterEvent(std::string node_id, std::string parent_id);
    void RemoveAttachLaterEvent(std::string node_id);
    AdGraphAPI::Node* GetAttachLaterParentNode(std::string node_id);

    void AddNotAddedScript(std::string node_id);
    bool CheckIfScriptIsNotAdded(std::string node_id);
    void AddNetworkRequestAttachLaterEvent(std::string node_id, Utilities::ordered_json json_item);
    void RemoveNetworkRequestAttachLaterEvent(std::string node_id);
    Utilities::ordered_json GetNetworkRequestAttachLaterEvent(std::string node_id);
    Utilities::ordered_json PrepareJSONVisualization();

    // Features
    Utilities::ordered_json GetGraphProperties();
    Utilities::ordered_json GetFirstParentProperties(AdGraphAPI::HTTPNode* http_node);
    Utilities::ordered_json GetSecondParentProperties(AdGraphAPI::HTTPNode* http_node);
    Utilities::ordered_json GetURLProperties(AdGraphAPI::HTTPNode* http_node);
    Utilities::ordered_json GetNodeProperties(AdGraphAPI::HTTPNode* http_node, std::string event_type);
    Utilities::ordered_json GetAscendantProperties(AdGraphAPI::HTTPNode* http_node, int level = 3);
    Utilities::ordered_json GetNumberOfDescendants(AdGraphAPI::HTTPNode* http_node, int level= 3);

    Utilities::ordered_json GetAllProperties(AdGraphAPI::HTTPNode* http_node, std::string event_type, int ascendant_level = 3, int descendant_level = 3);
    // int HTTPNode::MyDistanceFromRoot(){}

    // Timing
    Utilities::ordered_json GetTimingInfo();

  protected:
    std::map<std::string, AdGraphAPI::Node*> graph_;
    std::vector<std::tuple<std::string, std::string, std::string>> edge_list_;

    std::map<AdGraphAPI::HTMLNode*, AdGraphAPI::HTTPNode*> HTML_HTTP_node_map_;
    std::map<std::string, std::string> HTML_node_AttachLater_map_;
    std::set<std::string> node_ids_;
    std::set<std::string> HTML_node_ids_;
    std::set<std::string> HTTP_node_ids_;
    std::set<std::string> Script_node_ids_;
    std::string base_domain_;
    std::map<std::string, Utilities::ordered_json> Network_Request_AttachLater_map_;

    //Timing
    std::array<Utilities::uint64, 7> timing_vector_ = { {0, 0, 0, 0, 0, 0, 0} };

    // to keep katz centrality values
    std::map<AdGraphAPI::Node*, double> katz_centrality_map_;

    std::set<std::string> not_added_script_ids_;

    void AddNode(std::string id, AdGraphAPI::Node* node);

    Utilities::ordered_json ConstructGraphPropertiesObject();
    Utilities::ordered_json ConstructFirstParentPropertiesObject();
    Utilities::ordered_json ConstructSecondParentPropertiesObject();
    Utilities::ordered_json ConstructURLPropertiesObject();
    Utilities::ordered_json ConstructAscendantPropertiesObject();
    Utilities::ordered_json ConstructNodePropertiesObject();

    bool VerifyFirstParentPropertiesObject(Utilities::ordered_json json_object);
    bool VerifySecondParentPropertiesObject(Utilities::ordered_json json_object);

    double GetAverageDegreeConnectivity(AdGraphAPI::Node* node);
    void UpdateKatzCentrality(double alpha = 0.1, double beta = 1.0, int max_iter = 1000, double tol = 1.0e-6);

    std::tuple<bool, bool> ComputeScriptTextProperties(std::string script_text);
};

} // namespace AdGraphAPI
#endif // ADGRAPH

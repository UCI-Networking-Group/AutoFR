#ifndef JSONTOADGRAPHPARSER
#define JSONTOADGRAPHPARSER
#include <string>
#include <vector>
#include <map>

#include "utilities.h"
#include "adgraph.h"
#include "events_and_properties.h"

namespace AdGraphAPI
{

class JSONToAdGraphParser {
  public:
    JSONToAdGraphParser(std::string base_domain, std::string features_file_name, std::string url_id_string_map_file_name, std::string timing_file_name);
    void CreateGraph(Utilities::ordered_json json_content, std::map<std::string, int>& frame_script_count, std::string rendering_stream_directory);

  protected:
    AdGraph adgraph_;
    std::string features_file_name_;
    std::string url_id_string_map_file_name_;
    std::string visualization_file_name_;
    std::string timing_file_name_;
    std::tuple<std::string, bool, bool, bool, std::vector<std::string>, std::string> ExtractJSONPropertiesForHTMLNode(Utilities::ordered_json json_item);
    std::tuple<bool, std::string, bool, std::string, std::string> ExtractJSONPropertiesForHTTPNode(Utilities::ordered_json json_item);
    // std::tuple<int,  bool> ExtractJSONPropertiesForScriptNode(Utilities::ordered_json json_item);
    std::tuple<std::string, std::string> ExtractJSONPropertiesAttributes(Utilities::ordered_json json_item);
    std::vector<std::tuple<std::string, std::string, std::string>> edge_list_;
    std::tuple<std::vector<Utilities::ordered_json>, int> ParseJsonEvents(std::vector<Utilities::ordered_json> json_items, int current_url_counter);
};

} // namespace AdGraphAPI
#endif // JSONTOADGRAPHPARSER

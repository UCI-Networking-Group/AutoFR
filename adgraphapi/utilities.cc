#include "utilities.h"
#include "events_and_properties.h"
#include <sys/types.h>
#include <dirent.h>
#include <fstream>
#include <iomanip>

namespace AdGraphAPI {

    void Utilities::ReadDirectory(const std::string& name, std::vector<std::string>& v)
    {
        DIR* dirp = opendir(name.c_str());
        struct dirent * dp;
        while ((dp = readdir(dirp)) != NULL) {
            v.push_back(dp->d_name);
        }
        closedir(dirp);
    }

    Utilities::ordered_json Utilities::ReadJSON(std::string file_path){
        std::ifstream i(file_path);
        ordered_json json_content;
        i >> json_content;

        return json_content;
    }

    void Utilities::WriteJSON(std::string file_path, Utilities::ordered_json json_content) {
        std::ofstream o(file_path);    
        o << std::setw(4) << json_content << std::endl;
    }

    std::vector<std::string> Utilities::GetFrameScripts(Utilities::ordered_json json_content){  
        std::vector<std::string> frame_scripts;  
        for(auto& json_item : json_content["timeline"]) {
            
            if (json_item[EVENT_TYPE] == SCRIPT_COMPILATION)
                frame_scripts.push_back(json_item[SCRIPT_ID]);            
            
            else if (json_item[EVENT_TYPE] == SCRIPT_EVAL)
                frame_scripts.push_back(json_item[SCRIPT_ID]);
        }

        return frame_scripts;
    }

    Utilities::uint64 Utilities::GetTimeMs64() {
        #ifdef _WIN32
            /* Windows */
            FILETIME ft;
            LARGE_INTEGER li;

            /* Get the amount of 100 nano seconds intervals elapsed since January 1, 1601 (UTC) and copy it
        * to a LARGE_INTEGER structure. */
            GetSystemTimeAsFileTime(&ft);
            li.LowPart = ft.dwLowDateTime;
            li.HighPart = ft.dwHighDateTime;

            Utilities::uint64 ret = li.QuadPart;
            ret -= 116444736000000000LL; /* Convert from file time to UNIX epoch time. */
            ret /= 10000;                /* From 100 nano seconds (10^-7) to 1 millisecond (10^-3) intervals */

            return ret;
        #else
            /* Linux */
            struct timeval tv;

            gettimeofday(&tv, NULL);

            Utilities::uint64 ret = tv.tv_usec;
            /* Convert from micro seconds (10^-6) to milliseconds (10^-3) */
            ret /= 1000;

            /* Adds the seconds (10^0) after converting them to milliseconds (10^-3) */
            ret += (tv.tv_sec * 1000);

            return ret;
        #endif
    }

    void Utilities::AppendFeatures(std::string file_name, std::string string_to_write) {
        std::ofstream outfile;

        outfile.open(file_name, std::ios_base::app);
        outfile << string_to_write;     
    }

    void Utilities::WriteTimingInfo(std::string file_path, std::string base_domain, Utilities::ordered_json json_content){
        std::string string_to_write = "";

        string_to_write = base_domain + ","
                        + std::to_string(json_content["nodes"].get<int>()) + ","
                        + std::to_string(json_content["edges"].get<int>()) + ","
                        + std::to_string(json_content["url_nodes"].get<int>()) + ","

                        + std::to_string(json_content["overall_time"].get<int>() / (double)1000) + ","
                        + std::to_string(json_content["node_properties"].get<int>() / (double)1000) + ","
                        + std::to_string(json_content["first_parent_properties"].get<int>() / (double)1000) + ","
                        + std::to_string(json_content["second_parent_properties"].get<int>() / (double)1000) + ","
                        + std::to_string(json_content["url_properties"].get<int>() / (double)1000) + ","
                        + std::to_string(json_content["ascendant_properties"].get<int>() / (double)1000) + ","
                        + std::to_string(json_content["descendant_properties"].get<int>() / (double)1000) + ","
                        + std::to_string(json_content["katz_properties"].get<int>() / (double)1000)
                        + "\n"; 

        std::ofstream outfile;

        outfile.open(file_path, std::ios_base::app);
        outfile << string_to_write;    
    }
    
    void Utilities::WriteURLIdStringMapping(std::string url_id, std::string url_string, std::string file_name){
        std::ofstream outfile;

        outfile.open(file_name, std::ios_base::app);
        outfile << url_id + "," + url_string + "\n";    
    }

    void Utilities::WriteFeatures(Utilities::ordered_json feature_dictionary, std::string base_domain, std::string features_file_name){
        std::string row_to_write = "";         
//DOMAIN_NAME,NODE_ID,FEATURE_GRAPH_NODES,FEATURE_GRAPH_EDGES,FEATURE_GRAPH_NODES_EDGES,FEATURE_GRAPH_EDGES_NODES,FEATURE_INBOUND_CONNECTIONS,FEATURE_OUTBOUND_CONNECTIONS,FEATURE_INBOUND_OUTBOUND_CONNECTIONS,FEATURE_KATZ_CENTRALITY,FEATURE_AVERAGE_DEGREE_CONNECTIVITY,FEATURE_SCRIPT_IS_ACTIVE,FEATURE_SCRIPT_IS_EVAL_OR_FUNCTION,FEATURE_NODE_CATEGORY,FEATURE_DESCENDANTS,FEATURE_DESCENDANTS_OF_SCRIPT,FEATURE_ASCENDANTS_AD_KEYWORD,FEATURE_DESCENDANT_OF_EVAL_OR_FUNCTION,FEATURE_ASCENDANT_SCRIPT_HAS_EVAL_OR_FUNCTION,FEATURE_ASCENDANT_SCRIPT_HAS_FINGERPRINTING_KEYWORD,FEATURE_ASCENDANT_SCRIPT_LENGTH,FEATURE_FIRST_PARENT_ASYNC,FEATURE_FIRST_PARENT_DEFER,FEATURE_FIRST_PARENT_TAG_NAME,FEATURE_FIRST_NUMBER_OF_SIBLINGS,FEATURE_FIRST_PARENT_NUMBER_OF_SIBLINGS,FEATURE_FIRST_PARENT_SIBLING_TAG_NAME,FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE,FEATURE_FIRST_PARENT_INBOUND_CONNECTIONS,FEATURE_FIRST_PARENT_OUTBOUND_CONNECTIONS,FEATURE_FIRST_PARENT_INBOUND_OUTBOUND_CONNECTIONS,FEATURE_FIRST_PARENT_KATZ_CENTRALITY,FEATURE_FIRST_PARENT_AVERAGE_DEGREE_CONNECTIVITY,FEATURE_FIRST_PARENT_NODE_ADDED_BY_SCRIPT,FEATURE_FIRST_PARENT_NODE_REMOVED_BY_SCRIPT,FEATURE_FIRST_PARENT_ATTR_ADDED_BY_SCRIPT,FEATURE_FIRST_PARENT_ATTR_MODIFIED_BY_SCRIPT,FEATURE_FIRST_PARENT_ATTR_REMOVED_BY_SCRIPT,FEATURE_FIRST_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT,FEATURE_FIRST_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT,FEATURE_SECOND_PARENT_ASYNC,FEATURE_SECOND_PARENT_DEFER,FEATURE_SECOND_PARENT_TAG_NAME,FEATURE_SECOND_NUMBER_OF_SIBLINGS,FEATURE_SECOND_PARENT_NUMBER_OF_SIBLINGS,FEATURE_SECOND_PARENT_SIBLING_TAG_NAME,FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE,FEATURE_SECOND_PARENT_INBOUND_CONNECTIONS,FEATURE_SECOND_PARENT_OUTBOUND_CONNECTIONS,FEATURE_SECOND_PARENT_INBOUND_OUTBOUND_CONNECTIONS,FEATURE_SECOND_PARENT_KATZ_CENTRALITY,FEATURE_SECOND_PARENT_AVERAGE_DEGREE_CONNECTIVITY,FEATURE_SECOND_PARENT_NODE_ADDED_BY_SCRIPT,FEATURE_SECOND_PARENT_NODE_REMOVED_BY_SCRIPT,FEATURE_SECOND_PARENT_ATTR_ADDED_BY_SCRIPT,FEATURE_SECOND_PARENT_ATTR_MODIFIED_BY_SCRIPT,FEATURE_SECOND_PARENT_ATTR_REMOVED_BY_SCRIPT,FEATURE_SECOND_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT,FEATURE_SECOND_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT,FEATURE_AD_KEYWORD,FEATURE_SPECIAL_CHAR_AD_KEYWORD,FEATURE_SEMICOLON_PRESENT,FEATURE_VALID_QS,FEATURE_BASE_DOMAIN_IN_QS,FEATURE_AD_DIMENSIONS_IN_QS,FEATURE_AD_DIMENSIONS_IN_COMPLETE_URL,FEATURE_URL_LENGTH,FEATURE_SCREEN_DIMENSIONS_IN_QS,FEATURE_DOMAIN_PARTY,FEATURE_SUB_DOMAIN_CHECK,CLASS

        row_to_write = base_domain + ","
                    + feature_dictionary[LABEL_NODE_ID].get<std::string>() + "," 

                    + std::to_string(feature_dictionary[FEATURE_GRAPH_NODES].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_GRAPH_EDGES].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_GRAPH_NODES_EDGES].get<double>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_GRAPH_EDGES_NODES].get<double>()) + ","

                    + std::to_string(feature_dictionary[FEATURE_INBOUND_CONNECTIONS].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_OUTBOUND_CONNECTIONS].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_INBOUND_OUTBOUND_CONNECTIONS].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_KATZ_CENTRALITY].get<double>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_AVERAGE_DEGREE_CONNECTIVITY].get<double>()) + ","
                    + ((feature_dictionary[FEATURE_SCRIPT_IS_ACTIVE].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SCRIPT_IS_EVAL_OR_FUNCTION].get<bool>() == true) ? "1" : "0") + ","

                    + feature_dictionary[FEATURE_NODE_CATEGORY].get<std::string>() + ","

                    + std::to_string(feature_dictionary[FEATURE_DESCENDANTS].get<int>()) + ","
                    
                    + ((feature_dictionary[FEATURE_DESCENDANTS_OF_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_ASCENDANTS_AD_KEYWORD].get<bool>() == true) ? "1" : "0") + ","

                    + ((feature_dictionary[FEATURE_DESCENDANT_OF_EVAL_OR_FUNCTION].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_ASCENDANT_SCRIPT_HAS_EVAL_OR_FUNCTION].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_ASCENDANT_SCRIPT_HAS_FINGERPRINTING_KEYWORD].get<bool>() == true) ? "1" : "0") + ","
                    + std::to_string(feature_dictionary[FEATURE_ASCENDANT_SCRIPT_LENGTH].get<int>()) + ","
        
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_ASYNC].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_DEFER].get<bool>() == true) ? "1" : "0") + ","
                    + feature_dictionary[FEATURE_FIRST_PARENT_TAG_NAME].get<std::string>() + ","
                    + std::to_string(feature_dictionary[FEATURE_FIRST_NUMBER_OF_SIBLINGS].get<int>()) + ","
                    
                    + std::to_string(feature_dictionary[FEATURE_FIRST_PARENT_NUMBER_OF_SIBLINGS].get<int>()) + ","
                    + feature_dictionary[FEATURE_FIRST_PARENT_SIBLING_TAG_NAME].get<std::string>() + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_SIBLING_AD_ATTRIBUTE].get<bool>() == true) ? "1" : "0") + ","
        
                    + std::to_string(feature_dictionary[FEATURE_FIRST_PARENT_INBOUND_CONNECTIONS].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_FIRST_PARENT_OUTBOUND_CONNECTIONS].get<int>()) + ","

                    + std::to_string(feature_dictionary[FEATURE_FIRST_PARENT_INBOUND_OUTBOUND_CONNECTIONS].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_FIRST_PARENT_KATZ_CENTRALITY].get<double>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_FIRST_PARENT_AVERAGE_DEGREE_CONNECTIVITY].get<double>()) + ","

                    + ((feature_dictionary[FEATURE_FIRST_PARENT_NODE_ADDED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_NODE_REMOVED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_ATTR_ADDED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_ATTR_MODIFIED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_ATTR_REMOVED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_FIRST_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","

                    + ((feature_dictionary[FEATURE_SECOND_PARENT_ASYNC].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_DEFER].get<bool>() == true) ? "1" : "0") + ","
                    + feature_dictionary[FEATURE_SECOND_PARENT_TAG_NAME].get<std::string>() + ","
                    + std::to_string(feature_dictionary[FEATURE_SECOND_NUMBER_OF_SIBLINGS].get<int>()) + ","
                    
                    + std::to_string(feature_dictionary[FEATURE_SECOND_PARENT_NUMBER_OF_SIBLINGS].get<int>()) + ","
                    + feature_dictionary[FEATURE_SECOND_PARENT_SIBLING_TAG_NAME].get<std::string>() + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_SIBLING_AD_ATTRIBUTE].get<bool>() == true) ? "1" : "0") + ","

                    + std::to_string(feature_dictionary[FEATURE_SECOND_PARENT_INBOUND_CONNECTIONS].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_SECOND_PARENT_OUTBOUND_CONNECTIONS].get<int>()) + ","

                    + std::to_string(feature_dictionary[FEATURE_SECOND_PARENT_INBOUND_OUTBOUND_CONNECTIONS].get<int>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_SECOND_PARENT_KATZ_CENTRALITY].get<double>()) + ","
                    + std::to_string(feature_dictionary[FEATURE_SECOND_PARENT_AVERAGE_DEGREE_CONNECTIVITY].get<double>()) + ","

                    + ((feature_dictionary[FEATURE_SECOND_PARENT_NODE_ADDED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_NODE_REMOVED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_ATTR_ADDED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_ATTR_MODIFIED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_ATTR_REMOVED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_STYLE_ATTR_ADDED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SECOND_PARENT_STYLE_ATTR_REMOVED_BY_SCRIPT].get<bool>() == true) ? "1" : "0") + ","

                    + ((feature_dictionary[FEATURE_AD_KEYWORD].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SPECIAL_CHAR_AD_KEYWORD].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SEMICOLON_PRESENT].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_VALID_QS].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_BASE_DOMAIN_IN_QS].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_AD_DIMENSIONS_IN_QS].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_AD_DIMENSIONS_IN_COMPLETE_URL].get<bool>() == true) ? "1" : "0") + ","
                    
                    + std::to_string(feature_dictionary[FEATURE_URL_LENGTH].get<int>()) + ","

                    + ((feature_dictionary[FEATURE_SCREEN_DIMENSIONS_IN_QS].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_DOMAIN_PARTY].get<bool>() == true) ? "1" : "0") + ","
                    + ((feature_dictionary[FEATURE_SUB_DOMAIN_CHECK].get<bool>() == true) ? "1" : "0") + ","
                    + feature_dictionary[LABEL_NODE_CLASS].get<std::string>()
                    + "\n"; 
                    
        AppendFeatures(features_file_name, row_to_write);          
    }
} // namespace AdGraphAPI
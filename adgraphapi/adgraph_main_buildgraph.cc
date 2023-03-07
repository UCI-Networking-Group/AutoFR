#include <iostream>
#include "utilities.h"
#include "json_to_adgraph_parser.h"


int main(int argc,char* argv[])
{
    //"/mnt/drive/work/" -- "temp_map/"
    std::string base_directory = argv[1];
    std::string data_directory = base_directory + argv[2];
    std::string features_directory = base_directory + argv[3];
    std::string mapping_directory = base_directory + argv[4];
    std::string timing_file_name = base_directory + argv[5];

    std::vector<std::string> rendering_stream_directories;
    AdGraphAPI::Utilities::ReadDirectory(data_directory, rendering_stream_directories);

    std::vector<std::string> read_features_directories;
    AdGraphAPI::Utilities::ReadDirectory(features_directory, read_features_directories);
    bool features_already_computed = false;

    for (std::string &rendering_stream_directory : rendering_stream_directories)
    {
        features_already_computed = false;
        if (rendering_stream_directory == "." || rendering_stream_directory == ".." || rendering_stream_directory == ".DS_Store" )
            continue;
        std::cout << "\nProcessing: " << rendering_stream_directory << std::endl;

        if (read_features_directories.size() > 0) {

            for (std::string &read_features_directory : read_features_directories) {
                if(read_features_directory == rendering_stream_directory + ".csv"){
                    std::cout << "Features already computed" << std::endl;
                    features_already_computed = true;
                    break;
                }
            }
        }


        if(features_already_computed)
            continue;

        std::string current_path = data_directory + rendering_stream_directory;
        std::vector<std::string> current_directory_files;
        std::string largest_file_name = "";
        std::cout << "\n rendering stream directory " << data_directory + rendering_stream_directory << std::endl;

        AdGraphAPI::Utilities::ReadDirectory(data_directory + rendering_stream_directory, current_directory_files);

        AdGraphAPI::Utilities::ordered_json json_content;
        for(const std::string& file_name : current_directory_files){
            // std::cout << "\n" << file_name << std::endl;
            if (file_name.find("parsed_") != std::string::npos) {
                largest_file_name = file_name;
                break;
            }
        }

        if(largest_file_name == "")
            continue;

        std::vector<std::string> frame_scripts;
        std::map<std::string, int> frame_script_count;
        for(const std::string& file_name : current_directory_files){
            if (largest_file_name.size() > 7 && file_name.find(rendering_stream_directory) != std::string::npos && file_name != largest_file_name && file_name != largest_file_name.substr(7)) {
                frame_scripts = AdGraphAPI::Utilities::GetFrameScripts(AdGraphAPI::Utilities::ReadJSON(current_path + "/" + file_name));
            }
        }

        for(const std::string& script_id : frame_scripts){
            frame_script_count[script_id] = 0;
        }


        std::cout << "\n" << largest_file_name << std::endl;// << " , " << largest_file_lines << std::endl;
        json_content = AdGraphAPI::Utilities::ReadJSON(current_path + "/" + largest_file_name);

        AdGraphAPI::JSONToAdGraphParser parser_object(json_content["url"].get<std::string>(), features_directory + rendering_stream_directory + ".csv", mapping_directory + rendering_stream_directory, timing_file_name);

        parser_object.CreateGraph(json_content, frame_script_count, rendering_stream_directory);


        // break;
    }
}

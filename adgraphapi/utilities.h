#ifndef UTILITIES
#define UTILITIES
#include <string>
#include <vector>
#include <algorithm>

#include "fifo_map.hpp"
#include "json.hpp"


#ifdef _WIN32
#include <Windows.h>
#else
#include <sys/time.h>
#include <ctime>
#endif


namespace AdGraphAPI
{
class Utilities {
    public:
        // A workaround to give to use fifo_map as map, we are just ignoring the 'less' compare
        template<class K, class V, class dummy_compare, class A>
        using my_workaround_fifo_map = nlohmann::fifo_map<K, V, nlohmann::fifo_map_compare<K>, A>;
        using ordered_json = nlohmann::basic_json<my_workaround_fifo_map>;

        // typedef unsigned short int ShortInt;
        /* Remove if already defined */
        // typedef long long int64;
        typedef unsigned long long uint64;

        static Utilities::uint64 GetTimeMs64();

        static void ReadDirectory(const std::string& name, std::vector<std::string>& directories_vector);
        static ordered_json ReadJSON(std::string file_path);
        static void WriteJSON(std::string file_path, Utilities::ordered_json json_content);
        static void WriteTimingInfo(std::string file_path, std::string base_domain, Utilities::ordered_json json_content);
        static std::vector<std::string> GetFrameScripts(Utilities::ordered_json json_content);
        static void WriteFeatures(Utilities::ordered_json feature_dictionary, std::string base_domain, std::string features_file_name);
        static void AppendFeatures(std::string file_name, std::string string_to_write);
        static void WriteURLIdStringMapping(std::string url_id, std::string url_string, std::string file_name);
};

} // namespace AdGraphAPI
#endif // UTILITIES
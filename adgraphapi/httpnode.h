#ifndef HTTPNODE
#define HTTPNODE
#include "node.h"
#include "utilities.h"
#include <string>

namespace AdGraphAPI
{

class HTTPNode : public Node {
  public:
    HTTPNode(std::string id, bool script_is_active, std::string active_script_id, std::string url, bool ad, std::string requestor_id);

    bool GetScriptIsActiveStatus();
    std::string GetActiveScriptId();
    std::string GetURL();
    std::string GetRequestorId();
    bool GetAd();

  protected:
    bool script_is_active_;
    std::string active_script_id_;
    std::string url_;
    std::string requestor_id_;
    bool ad_;
};

} // namespace AdGraphAPI
#endif // HTTPNODE

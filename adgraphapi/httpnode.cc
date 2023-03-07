#include "httpnode.h"

namespace AdGraphAPI
{
    HTTPNode::HTTPNode(std::string id,
                    bool script_is_active,
                    std::string active_script_id,
                    std::string url,
                    bool ad,
                    std::string requestor_id) : Node(id),
                                        script_is_active_(script_is_active),
                                        active_script_id_(active_script_id),
                                        url_(url),
                                        ad_(ad),
                                        requestor_id_(requestor_id){}

    std::string HTTPNode::GetURL()
    {
        return url_;
    }

    bool HTTPNode::GetScriptIsActiveStatus(){
        return script_is_active_;
    }

    std::string HTTPNode::GetActiveScriptId(){
        return active_script_id_;
    }

   std::string HTTPNode::GetRequestorId(){
        return requestor_id_;
    }
    bool HTTPNode::GetAd(){
        return ad_;
    }

} // namespace AdGraphAPI



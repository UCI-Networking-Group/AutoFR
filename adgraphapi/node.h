#ifndef NODE
#define NODE
#include <string>
#include <vector>

namespace AdGraphAPI
{

class Node { 
  public:
    Node(std::string id);
    virtual void AddParent(AdGraphAPI::Node* parent);
    virtual void AddChild(AdGraphAPI::Node* child);

    std::string GetId();
    int GetInboundEdgeCount();
    int GetOutboundEdgeCount();

    std::vector<AdGraphAPI::Node*> GetParents();
    std::vector<AdGraphAPI::Node*> GetChilden();
  
  protected:
    std::string id_;
    std::vector<AdGraphAPI::Node*> parents_;
    std::vector<AdGraphAPI::Node*> children_;
};

} // namespace AdGraphAPI
#endif // NODE
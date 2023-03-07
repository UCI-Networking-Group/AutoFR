#include "node.h"

namespace AdGraphAPI 
{
    Node::Node(std::string id) : id_(id) {}

    void Node::AddParent(AdGraphAPI::Node* parent){
        parents_.push_back(parent);
    }
    
    void Node::AddChild(AdGraphAPI::Node* child){
        children_.push_back(child);
    }

    std::string Node::GetId(){
        return id_;
    }

    int Node::GetInboundEdgeCount(){
        return parents_.size();
    }

    int Node::GetOutboundEdgeCount(){
        return children_.size();
    }

    std::vector<AdGraphAPI::Node*> Node::GetParents(){
        return parents_;
    }

    std::vector<AdGraphAPI::Node*> Node::GetChilden(){
        return children_;
    }

} // namespace AdGraphAPI
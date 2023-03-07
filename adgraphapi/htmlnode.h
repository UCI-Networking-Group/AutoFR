#ifndef HTMLNODE
#define HTMLNODE
#include "node.h"
#include <string>

namespace AdGraphAPI
{

class HTMLNode : public Node {
  public:
    HTMLNode(std::string id, bool script_is_active, std::string tag_name, std::vector<std::string> attribute_name_and_values, std::string previous_sibling_id, bool async_script, bool defer_script);

    std::string GetTagName();
    std::vector<std::string> GetAttributeNameAndValues();
    std::string GetPreviousSiblingId();
    bool GetScriptIsActiveStatus();
    bool GetAsyncStatus();
    bool GetDeferStatus();

    bool GetHasAdKeyword();
    bool GetIsAdKeywordComputed();
    void SetHasAdKeyword(bool has_ad_keyword);
    void SetIsAdKeywordComputed(bool is_ad_keyword_computed);

    void AddAttributeNameAndValue(std::string attr);

    // AdGraphAPI::Node* GetLeftSibling();
    // AdGraphAPI::Node* GetRightSibling();
    bool GetNodeInsertionWithScriptStatus();
    bool GetNodeRemovalWithScriptStatus();
    bool GetAttributeAdditionWithScriptStatus();
    bool GetAttributeModificationWithScriptStatus();
    bool GetAttributeRemovalWithScriptStatus();
    bool GetAttributeStyleAdditionWithScriptStatus();
    bool GetAttributeStyleRemovalWithScriptStatus();
    bool GetIsFLGImage();
    bool GetIsFLGTextnode();
    bool GetIsFLGAd();
    std::string GetRequestedUrl();

    // void SetLeftSibling(AdGraphAPI::Node* left_sibling);
    // void SetRightSibling(AdGraphAPI::Node* right_sibling);

    void SetNodeInsertionWithScriptStatus(bool node_insertion_with_script);
    void SetNodeRemovalWithScriptStatus(bool node_removal_with_script);
    void SetAttributeAdditionWithScriptStatus(bool attribute_addition_with_script);
    void SetAttributeModificationWithScriptStatus(bool attribute_modification_with_script);
    void SetAttributeRemovalWithScriptStatus(bool attribute_removal_with_script);
    void SetAttributeStyleAdditionWithScriptStatus(bool attribute_style_addition_with_script);
    void SetAttributeStyleRemovalWithScriptStatus(bool attribute_style_removal_with_script);
    void SetIsFLGImage(bool is_flg_image);
    void SetIsFLGTextnode(bool is_flg_textnode);
    void SetIsFLGAd(bool is_flg_ad);
    void SetRequestedUrl(std::string requested_url);
  protected:
    std::string tag_name_;
    std::vector<std::string> attribute_name_and_values_;
    std::string previous_sibling_id_;
    bool script_is_active_;
    bool async_script_;
    bool defer_script_;
    bool has_ad_keyword_;
    bool is_ad_keyword_computed_;

    // Need them for features i.e. only HTTP nodes.
    // But HTTP nodes are not going to have siblings.
    // We can look for the siblings of its parent.
    // But how many parents?
    // Also only keep ids which is O(1) instead of reference.

    // AdGraphAPI::Node* left_sibling_;
    // AdGraphAPI::Node* right_sibling_;

    // Also HTTP nodes cannot have these features.
    // Need them for their parents.
    bool node_insertion_with_script_;
    bool node_removal_with_script_;
    bool attribute_addition_with_script_;
    bool attribute_modification_with_script_;
    bool attribute_removal_with_script_;
    bool attribute_style_addition_with_script_;
    bool attribute_style_removal_with_script_;
    bool is_flg_image_;
    bool is_flg_textnode_;
    bool is_flg_ad_;
    std::string requested_url_;
};

} // namespace AdGraphAPI
#endif // HTMLNODE

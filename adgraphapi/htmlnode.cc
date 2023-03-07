#include "htmlnode.h"

namespace AdGraphAPI
{
    HTMLNode::HTMLNode(std::string id,
                    bool script_is_active,
                    std::string tag_name,
                    std::vector<std::string> attribute_name_and_values,
                    std::string previous_sibling_id,
                    bool async_script,
                    bool defer_script) : Node(id),
                                        script_is_active_(script_is_active),
                                        tag_name_(tag_name),
                                        attribute_name_and_values_(attribute_name_and_values),
                                        previous_sibling_id_(previous_sibling_id),
                                        async_script_(async_script),
                                        defer_script_(defer_script),
                                        is_ad_keyword_computed_(false),
                                        node_insertion_with_script_(false),
                                        node_removal_with_script_(false),
                                        attribute_addition_with_script_(false),
                                        attribute_modification_with_script_(false),
                                        attribute_removal_with_script_(false),
                                        attribute_style_addition_with_script_(false),
                                        attribute_style_removal_with_script_(false),
                                        is_flg_image_(false),
                                        is_flg_textnode_(false),
                                        is_flg_ad_(false),
                                        requested_url_(""){}

    std::string HTMLNode::GetTagName()
    {
        return tag_name_;
    }

    std::vector<std::string> HTMLNode::GetAttributeNameAndValues(){
        return attribute_name_and_values_;
    }

    std::string HTMLNode::GetPreviousSiblingId(){
        return previous_sibling_id_;
    }

    bool HTMLNode::GetScriptIsActiveStatus(){
        return script_is_active_;
    }

    bool HTMLNode::GetAsyncStatus(){
        return async_script_;
    }

    bool HTMLNode::GetDeferStatus(){
        return defer_script_;
    }

    void HTMLNode::AddAttributeNameAndValue(std::string attr){
        attribute_name_and_values_.push_back(attr);
    }

    // AdGraphAPI::Node* HTMLNode::GetLeftSibling(){
    //     return left_sibling_;
    // }

    // AdGraphAPI::Node* HTMLNode::GetRightSibling(){
    //     return right_sibling_;
    // }

    bool HTMLNode::GetNodeInsertionWithScriptStatus(){
        return node_insertion_with_script_;
    }

    bool HTMLNode::GetNodeRemovalWithScriptStatus(){
        return node_removal_with_script_;
    }

    bool HTMLNode::GetAttributeAdditionWithScriptStatus(){
        return attribute_addition_with_script_;
    }

    bool HTMLNode::GetAttributeModificationWithScriptStatus(){
        return attribute_modification_with_script_;
    }

    bool HTMLNode::GetAttributeRemovalWithScriptStatus(){
        return attribute_removal_with_script_;
    }

    bool HTMLNode::GetAttributeStyleAdditionWithScriptStatus(){
        return attribute_style_addition_with_script_;
    }

    bool HTMLNode::GetAttributeStyleRemovalWithScriptStatus(){
        return attribute_style_removal_with_script_;
    }
    bool HTMLNode::GetIsFLGImage(){
        return is_flg_image_;
    }
    bool HTMLNode::GetIsFLGTextnode(){
        return is_flg_textnode_;
    }
    bool HTMLNode::GetIsFLGAd(){
        return is_flg_ad_;
    }
    std::string HTMLNode::GetRequestedUrl(){
        return requested_url_;
    }
    // void HTMLNode::SetLeftSibling(AdGraphAPI::Node* left_sibling){
    //     left_sibling_ = left_sibling;
    // }

    // void HTMLNode::SetRightSibling(AdGraphAPI::Node* right_sibling){
    //     right_sibling_ = right_sibling;
    // }

    bool HTMLNode::GetHasAdKeyword(){
        return has_ad_keyword_;
    }

    bool HTMLNode::GetIsAdKeywordComputed(){
        return is_ad_keyword_computed_;
    }

    void HTMLNode::SetHasAdKeyword(bool has_ad_keyword){
        has_ad_keyword_ = has_ad_keyword;
    }

    void HTMLNode::SetIsAdKeywordComputed(bool is_ad_keyword_computed){
        is_ad_keyword_computed_ = is_ad_keyword_computed;
    }

    void HTMLNode::SetNodeInsertionWithScriptStatus(bool node_insertion_with_script){
        node_insertion_with_script_ = node_insertion_with_script;
    }

    void HTMLNode::SetNodeRemovalWithScriptStatus(bool node_removal_with_script){
        node_removal_with_script_ = node_removal_with_script;
    }

    void HTMLNode::SetAttributeAdditionWithScriptStatus(bool attribute_addition_with_script){
        attribute_addition_with_script_ = attribute_addition_with_script;
    }

    void HTMLNode::SetAttributeModificationWithScriptStatus(bool attribute_modification_with_script){
        attribute_modification_with_script_ = attribute_modification_with_script;
    }

    void HTMLNode::SetAttributeRemovalWithScriptStatus(bool attribute_removal_with_script){
        attribute_removal_with_script_ = attribute_removal_with_script;
    }

    void HTMLNode::SetAttributeStyleAdditionWithScriptStatus(bool attribute_style_addition_with_script){
        attribute_style_addition_with_script_ = attribute_style_addition_with_script;
    }

    void HTMLNode::SetAttributeStyleRemovalWithScriptStatus(bool attribute_style_removal_with_script){
        attribute_style_removal_with_script_ = attribute_style_removal_with_script;
    }
    void HTMLNode::SetIsFLGImage(bool is_flg_image){
        is_flg_image_ = is_flg_image;
    }
    void HTMLNode::SetIsFLGTextnode(bool is_flg_textnode){
        is_flg_textnode_ = is_flg_textnode;
    }
    void HTMLNode::SetIsFLGAd(bool is_flg_ad){
        is_flg_ad_ = is_flg_ad;
    }
    void HTMLNode::SetRequestedUrl(std::string requested_url){
        requested_url_ = requested_url;
    }
} // namespace AdGraphAPI



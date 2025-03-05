from flask import Flask, redirect, url_for, render_template, request
from functions import (
    initialize_conversation,
    initialize_conv_reco,
    get_chat_model_completions,
    moderation_check,
    intent_confirmation_layer,
    compare_laptops_with_user,
    recommendation_validation,
    get_user_requirement_string,
    get_chat_completions_func_calling
)
import openai
import ast
import re
import pandas as pd
import json

# Set OpenAI API key (adjust the path if needed based on your setup)
openai.api_key = open("OpenAI_API_Key.txt", 'r').read().strip()

app = Flask(__name__)

# Global variables to maintain conversation state
conversation_bot = []  # Stores the UI-facing conversation (user and bot messages)
conversation = initialize_conversation()  # Stores the OpenAI chat model conversation
introduction = get_chat_model_completions(conversation)  # Initial welcome message
conversation_bot.append({'bot': introduction})  # Add welcome message to UI
top_3_laptops = None  # Holds laptop recommendations once generated
conversation_reco = None  # Holds recommendation-specific conversation

@app.route("/")
def default_func():
    global conversation_bot, conversation, top_3_laptops, conversation_reco
    return render_template("conversation_bot.html", name_xyz=conversation_bot)

@app.route("/end_conversation", methods=['POST', 'GET'])
def end_conv():
    global conversation_bot, conversation, top_3_laptops, conversation_reco
    # Reset all conversation state
    conversation_bot = []
    conversation = initialize_conversation()
    introduction = get_chat_model_completions(conversation)
    conversation_bot.append({'bot': introduction})
    top_3_laptops = None
    conversation_reco = None
    return redirect(url_for('default_func'))

@app.route("/conversation", methods=['POST'])
def invite():
    global conversation_bot, conversation, top_3_laptops, conversation_reco
    user_input = request.form["user_input_message"]
    prompt = 'Remember your system message and that you are an intelligent laptop assistant. So, you only help with questions around laptop.'
    
    # Moderation check for user input
    moderation = moderation_check(user_input)
    if moderation == 'Flagged':
        return redirect(url_for('end_conv'))

    # Append user message to UI immediately (server-side)
    conversation_bot.append({'user': user_input})

    # Handle conversation flow based on whether laptops have been recommended yet
    if top_3_laptops is None:
        # Initial conversation phase: gathering requirements
        conversation.append({"role": "user", "content": user_input + prompt})
        
        # Get bot response from OpenAI
        response_assistant = get_chat_model_completions(conversation)

        # Moderation check for bot response
        moderation = moderation_check(response_assistant)
        if moderation == 'Flagged':
            return redirect(url_for('end_conv'))

        # Check if intent is confirmed
        confirmation = intent_confirmation_layer(response_assistant)    

        moderation = moderation_check(confirmation)
        if moderation == 'Flagged':
            return redirect(url_for('end_conv'))

        if "No" in confirmation:
            # Intent not confirmed, continue asking questions
            conversation.append({"role": "assistant", "content": response_assistant})
            conversation_bot.append({'bot': response_assistant})
        else:
            # Intent confirmed, extract requirements and recommend laptops
            response = get_user_requirement_string(response_assistant)
            result = get_chat_completions_func_calling(response, True)
            conversation_bot.append({'bot': "Thank you for providing all the information. Kindly wait, while I fetch the products: \n"})
            
            top_3_laptops = compare_laptops_with_user(result)
            validated_reco = recommendation_validation(top_3_laptops)

            if len(validated_reco) == 0:
                conversation_bot.append({'bot': "Sorry, we do not have laptops that match your requirements. Connecting you to a human expert. Please end this conversation."})
            else:
                conversation_reco = initialize_conv_reco(validated_reco)
                recommendation = get_chat_model_completions(conversation_reco)

                moderation = moderation_check(recommendation)
                if moderation == 'Flagged':
                    return redirect(url_for('end_conv'))

                conversation_reco.append({"role": "user", "content": "This is my user profile" + response})
                conversation_reco.append({"role": "assistant", "content": recommendation})
                conversation_bot.append({'bot': recommendation})

    else:
        # Recommendation phase: answering questions about recommended laptops
        if conversation_reco is None:
            conversation_reco = initialize_conv_reco(top_3_laptops)
        
        conversation_reco.append({"role": "user", "content": user_input})
        conversation_bot.append({'user': user_input})

        response_asst_reco = get_chat_model_completions(conversation_reco)

        moderation = moderation_check(response_asst_reco)
        if moderation == 'Flagged':
            return redirect(url_for('end_conv'))

        conversation_reco.append({"role": "assistant", "content": response_asst_reco})
        conversation_bot.append({'bot': response_asst_reco})

    return redirect(url_for('default_func'))

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)
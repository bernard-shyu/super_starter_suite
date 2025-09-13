import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class TestChatInterface(unittest.TestCase):

    def setUp(self):
        options = Options()
        options.add_argument("--user-data-dir=/tmp/chrome_user_data")
        service = Service('/path/to/chromedriver')  # Replace with the actual path to chromedriver
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.get("http://localhost:8000")  # Replace with the actual URL

    def test_message_display(self):
        # Test if messages are displayed correctly
        message_input = self.driver.find_element(By.ID, "message-input")
        message_input.send_keys("Hello, AI!")
        message_input.send_keys(Keys.RETURN)

        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "message-bubble"))
        )

        messages = self.driver.find_elements(By.CLASS_NAME, "message-bubble")
        self.assertGreater(len(messages), 0, "No messages displayed")

    def test_message_history(self):
        # Test if message history is maintained
        message_input = self.driver.find_element(By.ID, "message-input")
        message_input.send_keys("Hello, AI!")
        message_input.send_keys(Keys.RETURN)

        message_input.send_keys("How are you?")
        message_input.send_keys(Keys.RETURN)

        messages = self.driver.find_elements(By.CLASS_NAME, "message-bubble")
        self.assertGreater(len(messages), 1, "Message history not maintained")

    def test_error_handling(self):
        # Test error handling for invalid inputs
        message_input = self.driver.find_element(By.ID, "message-input")
        message_input.send_keys("Invalid input")
        message_input.send_keys(Keys.RETURN)

        error_message = self.driver.find_element(By.ID, "error-message")
        self.assertIsNotNone(error_message, "Error message not displayed")

    def tearDown(self):
        self.driver.quit()

if __name__ == "__main__":
    unittest.main()
